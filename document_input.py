"""Validate and extract startup fields from uploaded PDF and Excel documents."""

from io import BytesIO
import math
import re
import zipfile

MAX_UPLOAD_SIZE = 10 * 1024 * 1024

_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".xls": {"application/vnd.ms-excel", "application/x-ole-storage"},
}
_ALIASES = {
    "startup_name": {"startupname", "companyname", "businessname"},
    "industry": {"industry", "sector", "marketsector"},
    "funding_amount": {"funding", "fundingamount", "fundingamountinr", "amountraised", "totalfunding"},
    "employees_count": {"employees", "employeecount", "employeescount", "numberofemployees", "numemployees", "teamsize"},
    "revenue": {"revenue", "annualrevenue"},
    "city": {"location", "city", "headquarters", "hq"},
    "founder_experience": {"founderexperience", "founderexperienceyears", "yearsoffounderexperience"},
    "market_size": {"marketsize", "market", "marketpotential"},
    "product_uniqueness_score": {"productuniquenessscore", "uniquenessscore", "productuniqueness"},
    "startup_age": {"startupage", "startupageyears", "yearsoperation", "yearsinoperation", "yearsoperating"},
    "customer_retention_rate": {"customerretentionrate", "retentionrate"},
    "marketing_expense": {"marketingexpense", "marketingcost"},
    "burn_rate": {"burnrate", "monthlyburnrate"},
    "number_of_founders": {"numberoffounders", "foundercount", "founders"},
    "funding_round": {"fundinground", "round"},
}
_NUMBER_FIELDS = {
    "funding_amount", "employees_count", "revenue", "founder_experience", "product_uniqueness_score",
    "startup_age", "customer_retention_rate", "marketing_expense", "burn_rate", "number_of_founders",
}


def extract_uploaded_document(filename, content_type, content):
    """Validate uploaded bytes and return canonical startup fields and source metadata."""
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in _MIME_TYPES:
        raise ValueError("Only PDF, XLSX, and XLS files are supported.")
    if content_type not in _MIME_TYPES[extension]:
        raise ValueError("The uploaded file MIME type does not match its extension.")
    if not content:
        raise ValueError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_SIZE:
        raise ValueError("Files must be 10 MB or smaller.")

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("The uploaded file is not a valid PDF.")
        records, source = _extract_pdf(content)
    elif extension == ".xlsx":
        if not content.startswith(b"PK"):
            raise ValueError("The uploaded file is not a valid XLSX workbook.")
        records, source = _extract_xlsx(content)
    else:
        if not content.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise ValueError("The uploaded file is not a valid XLS workbook.")
        records, source = _extract_xls(content)

    if not records or not any(records):
        raise ValueError("No supported startup fields were found in the uploaded file.")
    return {"fields": records[0], "records": records, "source": source}


def _normalize_label(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _canonical_field(label):
    normalized = _normalize_label(label)
    return next((field for field, aliases in _ALIASES.items() if normalized in aliases), None)


def _clean_value(field, value):
    if value is None:
        return None
    if isinstance(value, str):
        value = " ".join(value.split())
    if value == "":
        return None
    if field not in _NUMBER_FIELDS:
        return value
    if isinstance(value, bool):
        raise ValueError(f"The {field.replace('_', ' ')} value is invalid.")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        cleaned = re.sub(r"[^0-9.+-]", "", str(value).replace(",", ""))
        try:
            number = float(cleaned)
        except ValueError as exc:
            raise ValueError(f"The {field.replace('_', ' ')} value is not numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"The {field.replace('_', ' ')} value is invalid.")
    if number < 0:
        raise ValueError(f"The {field.replace('_', ' ')} value cannot be negative.")
    if field in {"employees_count", "number_of_founders"}:
        if not number.is_integer():
            raise ValueError(f"The {field.replace('_', ' ')} value must be a whole number.")
        return int(number)
    return number


def _merge_fields(target, values):
    for field, value in values.items():
        cleaned = _clean_value(field, value)
        if cleaned is None:
            continue
        previous = target.get(field)
        if previous is not None and str(previous).casefold() != str(cleaned).casefold():
            raise ValueError(f"The uploaded file has conflicting values for {field.replace('_', ' ')}.")
        target[field] = cleaned


def _records_from_label_lines(lines):
    records = []
    current = {}
    for line in lines:
        parts = re.split(r"\s*[:=|\t]\s*", line, maxsplit=1)
        if len(parts) != 2:
            aligned = re.match(r"^(.+?)\s{2,}(.+)$", line.strip())
            if aligned:
                parts = [aligned.group(1), aligned.group(2)]
        if len(parts) != 2:
            continue
        field = _canonical_field(parts[0])
        if not field:
            continue
        if field == "startup_name" and current:
            records.append(current)
            current = {}
        _merge_fields(current, {field: parts[1]})
    if current:
        records.append(current)
    return records


def _extract_pdf(content):
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")
        page_text = []
        image_page_without_text = False
        for page in reader.pages:
            text = page.extract_text() or ""
            page_text.append("\n".join(line.strip() for line in text.splitlines() if line.strip()))
            if not text.strip() and _page_has_image(page):
                image_page_without_text = True
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The PDF is malformed or could not be read.") from exc

    extracted_text = "\n".join(text for text in page_text if text)
    if not extracted_text:
        if any(_page_has_image(page) for page in reader.pages):
            raise ValueError("This PDF appears to contain scanned images; OCR is required.")
        raise ValueError("The PDF contains no extractable text.")
    if image_page_without_text:
        raise ValueError("Some PDF pages appear to be scanned images; OCR is required.")

    records = _records_from_label_lines(extracted_text.splitlines())
    return records, {"type": "pdf", "pages": len(reader.pages)}


def _page_has_image(page):
    try:
        resources = page.get("/Resources")
        if resources is None:
            return False
        xobjects = resources.get_object().get("/XObject")
        if xobjects is None:
            return False
        return any(
            item.get_object().get("/Subtype") == "/Image"
            for item in xobjects.get_object().values()
        )
    except Exception:
        return False


def _extract_xlsx(content):
    from openpyxl import load_workbook

    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if "xl/workbook.xml" not in archive.namelist() or "[Content_Types].xml" not in archive.namelist():
                raise ValueError("The uploaded file is not a valid XLSX workbook.")
            if sum(info.file_size for info in archive.infolist()) > 50 * 1024 * 1024:
                raise ValueError("The workbook expands beyond the supported processing limit.")
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        sheet_names = list(workbook.sheetnames)
        sheet_records = []
        tables = []
        for worksheet in workbook.worksheets:
            rows = []
            cell_count = 0
            for row_number, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
                cell_count += len(row)
                if row_number > 500000 or cell_count > 500000:
                    raise ValueError("A worksheet exceeds the supported processing limit.")
                rows.append(list(row))
            sheet_records.append(_records_from_worksheet(rows))
            header_index = next(
                (
                    index
                    for index, row in enumerate(rows)
                    if sum(_canonical_field(value) is not None for value in row) >= 2
                ),
                None,
            )
            tables.append({
                "name": worksheet.title,
                "header_row": header_index,
                "headers": [str(value) if value is not None else "" for value in rows[header_index]]
                if header_index is not None else [],
                "rows": [[_serialize_cell(value) for value in row] for row in rows],
            })
        workbook.close()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The XLSX workbook is malformed or could not be read.") from exc
    records = _combine_sheet_records(sheet_records)
    return records, {"type": "xlsx", "sheets": sheet_names, "tables": tables}


def _extract_xls(content):
    import xlrd

    try:
        workbook = xlrd.open_workbook(file_contents=content, on_demand=True)
        sheet_names = workbook.sheet_names()
        sheet_records = []
        tables = []
        for sheet_name in sheet_names:
            worksheet = workbook.sheet_by_name(sheet_name)
            if worksheet.nrows * worksheet.ncols > 500000:
                raise ValueError("A worksheet exceeds the supported processing limit.")
            rows = [worksheet.row_values(row_number) for row_number in range(worksheet.nrows)]
            sheet_records.append(_records_from_worksheet(rows))
            header_index = next(
                (
                    index
                    for index, row in enumerate(rows)
                    if sum(_canonical_field(value) is not None for value in row) >= 2
                ),
                None,
            )
            tables.append({
                "name": sheet_name,
                "header_row": header_index,
                "headers": [str(value) if value is not None else "" for value in rows[header_index]]
                if header_index is not None else [],
                "rows": [
                    [_xls_cell_value(workbook, worksheet, row_index, column_index)
                     for column_index in range(worksheet.ncols)]
                    for row_index in range(worksheet.nrows)
                ],
            })
        workbook.release_resources()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The XLS workbook is malformed or could not be read.") from exc
    records = _combine_sheet_records(sheet_records)
    return records, {"type": "xls", "sheets": sheet_names, "tables": tables}


def _serialize_cell(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _xls_cell_value(workbook, worksheet, row_index, column_index):
    import xlrd

    cell = worksheet.cell(row_index, column_index)
    if cell.ctype == 3:
        return xlrd.xldate.xldate_as_datetime(cell.value, workbook.datemode).isoformat()
    if cell.ctype == 4:
        return bool(cell.value)
    if cell.ctype == 5:
        return xlrd.biffh.error_text_from_code.get(cell.value, "#ERROR")
    if cell.ctype in (0, 6):
        return None
    return cell.value


def _records_from_worksheet(rows):
    for row_index, row in enumerate(rows):
        recognized = [_canonical_field(value) for value in row]
        if any(field is not None for field in recognized):
            records = []
            for data_row in rows[row_index + 1:]:
                candidate = {
                    field: data_row[column_index]
                    for column_index, field in enumerate(recognized)
                    if field and column_index < len(data_row)
                }
                candidate = {field: value for field, value in candidate.items() if value not in (None, "")}
                if candidate:
                    cleaned = {}
                    _merge_fields(cleaned, candidate)
                    records.append(cleaned)
            return records
    return _records_from_label_lines(
        [f"{row[0]}: {row[1]}" for row in rows if len(row) >= 2 and row[1] not in (None, "")]
    )


def _combine_sheet_records(sheet_records):
    combined = []
    for records in sheet_records:
        for row_index, record in enumerate(records):
            if row_index == len(combined):
                combined.append({})
            _merge_fields(combined[row_index], record)
    return combined