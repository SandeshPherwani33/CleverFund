from io import BytesIO
import base64
from datetime import date
import os
import sys
import zlib
from types import SimpleNamespace

import pytest
from openpyxl import Workbook
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from sklearn.preprocessing import LabelEncoder

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from document_input import MAX_UPLOAD_SIZE, extract_uploaded_document

MODEL_FEATURES = [
    "funding_amount", "employees_count", "industry", "revenue", "city", "founder_experience",
    "market_size", "product_uniqueness_score", "startup_age", "customer_retention_rate",
    "marketing_expense", "burn_rate", "number_of_founders",
]


def model_metadata():
    return {
        "feature_cols": MODEL_FEATURES,
        "label_encoders": {
            name: LabelEncoder().fit(categories)
            for name, categories in {
                "industry": ["Technology", "Retail"],
                "city": ["Austin", "Boston"],
                "market_size": ["Large", "Medium", "Small", "Very Large"],
            }.items()
        },
    }


def make_startup_record(name="Northstar", **overrides):
    record = {
        "startup_name": name,
        "funding_amount": 1250000,
        "employees_count": 12,
        "industry": "Technology",
        "revenue": 250000,
        "city": "Boston",
        "founder_experience": 5,
        "market_size": "Large",
        "product_uniqueness_score": 8,
        "startup_age": 2.5,
        "customer_retention_rate": 0.8,
        "marketing_expense": 10000,
        "burn_rate": 50000,
        "number_of_founders": 2,
    }
    record.update(overrides)
    return record


def workbook_for_records(records):
    labels = {
        "startup_name": "Startup Name",
        "funding_amount": "Funding Amount",
        "employees_count": "Employees",
        "industry": "Industry",
        "revenue": "Revenue",
        "city": "City",
        "founder_experience": "Founder Experience",
        "market_size": "Market Size",
        "product_uniqueness_score": "Product Uniqueness Score",
        "startup_age": "Startup Age",
        "customer_retention_rate": "Customer Retention Rate",
        "marketing_expense": "Marketing Expense",
        "burn_rate": "Burn Rate",
        "number_of_founders": "Number of Founders",
    }
    columns = list(records[0])
    rows = [[labels[column] for column in columns]]
    rows.extend([[record.get(column) for column in columns] for record in records])
    return make_xlsx([("Startups", rows)])


def make_xlsx(sheets):
    workbook = Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets:
        worksheet = workbook.create_sheet(name)
        for row in rows:
            worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def make_pdf(pages):
    output = BytesIO()
    pdf = canvas.Canvas(output)
    for lines in pages:
        for index, line in enumerate(lines):
            pdf.drawString(50, 780 - index * 20, line)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


class OversizedContent:
    def __bool__(self):
        return True

    def __len__(self):
        return MAX_UPLOAD_SIZE + 1


def test_extract_xlsx_across_multiple_worksheets():
    content = make_xlsx([
        ("Company", [["Startup Name", "Industry", "Location"], ["Northstar", "Technology", "Boston"]]),
        ("Metrics", [["Funding Amount", "Employees", "Revenue", "Founded"], [1250000, 12, 250000, date(2025, 1, 2)]]),
    ])

    result = extract_uploaded_document(
        "startup.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content,
    )

    assert result["fields"] == {
        "startup_name": "Northstar",
        "industry": "Technology",
        "city": "Boston",
        "funding_amount": 1250000.0,
        "employees_count": 12,
        "revenue": 250000.0,
    }
    assert result["source"]["sheets"] == ["Company", "Metrics"]
    assert result["source"]["tables"][0]["headers"] == ["Startup Name", "Industry", "Location"]
    assert result["source"]["tables"][1]["rows"][1] == [1250000, 12, 250000, "2025-01-02T00:00:00"]


def test_extract_valid_xls():
    content = zlib.decompress(base64.b64decode(
        "eNrtWE9IFFEY/73Z/4uuq2mkhSxCVualunTR1QWVyBazoIig1t1BxXVGZmeF7ZJlewyCTkUXwUsXq0t/qKBuHQKjDkEQaB07BQUddKfvfTsja3lwoaRkfsP73vd973vvezPf996bmTeL9UtzD1qW8Qu64UHJCsFfoRNUQo4QBbVblmSdOkjFcvFfIRSkQPp9eFr7OiBjKOO9DAX3vS+JAp+onMcUkrqmxrYQCZ5DSsg5dBEVuEOaCJp5Vg1M00x3ML3Hls+Y9rDmOtMusl0S57AYT3YctbP4rNLGbRHIcR9xnw+sOYQmvJJZfPmGKNv60GuMp7L/ZkOrtwbzoLgNqJpqpLJLaKQAzuO7FQO+OSv1RczVb61egPQ/1usDG+hvKl5gBtZFTvAi6rDHK1sCOGWmDDM/tYJp3nFlqYGjjSVTkypttse0TD5nGoUI0J/XMuPaaKx3Us9rJpn3TU5l9YKq5ig7htVpVcvLHoN6OmWO6xoZJHXDHMvRgGHgtJoe0/SsPlqg5Z/Qc6auhaVX3hui6/aGWl4zNUQzNF3J1/PKidLuv3L369sTI0PxC6yZ4fOgfGrslTcKC1dkD+oc4RYFzqgdzB9kepVH3c18C9NGyneq24eabKZ/lm2ucWs7+TnCeBffV8HvJ7745eTj1uLn+AHiFwaWLzUuvI/PoY2eZ4b6y2sWnaJT3L4l8STu1MLeYT4ybf5ttwkqUXvuln001mEVYWbrmZYl+XTEmqTYz6oseUjyrElekrxrko8kn+1HbOBHsB+/bS/YjwzRc+wiXvpJHB8kepjtEok6GrtsKUeWcelWGvCQA9BTccKH4cKFCxcuXLhw4WJ7Q9jv4R5+BwW/dfr5E6T8X2eVSsn9TbJtMQydLpM+TPugUW2gUFX+7IRPOGOJTfZx/hdKnCHvBiYwwvOYqDp/6TtNVN7PpjtG/9wSqtZ/qZp5/mX/PwE9Uea5"
    ))
    result = extract_uploaded_document("startup.xls", "application/vnd.ms-excel", content)

    assert result["fields"]["startup_name"] == "Northstar"
    assert result["fields"]["funding_amount"] == 1250000.0
    assert result["fields"]["employees_count"] == 12
    assert result["source"]["sheets"] == ["Startup"]


def test_extract_pdf_text_from_all_pages():
    content = make_pdf([
        ["Startup Name: Northstar", "Funding Amount: 1250000"],
        ["Industry: Technology", "Employees: 12", "Revenue: 250000", "Location: Boston"],
    ])
    result = extract_uploaded_document("startup.pdf", "application/pdf", content)

    assert result["fields"] == {
        "startup_name": "Northstar",
        "funding_amount": 1250000.0,
        "industry": "Technology",
        "employees_count": 12,
        "revenue": 250000.0,
        "city": "Boston",
    }
    assert result["source"]["pages"] == 2


def test_extract_pipe_separated_pdf_table_values():
    content = make_pdf([[
        "Startup Name | Northstar",
        "Funding Amount | 1250000",
        "Employees | 12",
    ]])
    result = extract_uploaded_document("startup.pdf", "application/pdf", content)
    assert result["fields"]["startup_name"] == "Northstar"
    assert result["fields"]["funding_amount"] == 1250000.0
    assert result["fields"]["employees_count"] == 12


def test_detect_scanned_and_encrypted_pdfs():
    image_data = BytesIO()
    Image.new("RGB", (2, 2), "white").save(image_data, format="PNG")
    scanned_pdf = BytesIO()
    pdf = canvas.Canvas(scanned_pdf)
    pdf.drawImage(ImageReader(BytesIO(image_data.getvalue())), 0, 0)
    pdf.save()
    with pytest.raises(ValueError, match="OCR is required"):
        extract_uploaded_document("scan.pdf", "application/pdf", scanned_pdf.getvalue())

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    encrypted_pdf = BytesIO()
    writer.write(encrypted_pdf)
    with pytest.raises(ValueError, match="Encrypted PDFs"):
        extract_uploaded_document("locked.pdf", "application/pdf", encrypted_pdf.getvalue())


def test_reject_empty_pdf_and_misleading_pdf_content():
    with pytest.raises(ValueError, match="no extractable text"):
        extract_uploaded_document("empty.pdf", "application/pdf", make_pdf([[]]))
    with pytest.raises(ValueError, match="not a valid PDF"):
        extract_uploaded_document("fake.pdf", "application/pdf", b"PK\x03\x04not a PDF")


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "message"),
    [
        ("bad.pdf", "application/pdf", b"not a pdf", "not a valid PDF"),
        ("bad.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"not a zip", "not a valid XLSX"),
        ("bad.xls", "application/vnd.ms-excel", b"not an OLE file", "not a valid XLS"),
        ("fake.pdf", "text/plain", b"%PDF-1.4", "MIME type"),
        ("unsupported.csv", "text/csv", b"data", "Only PDF"),
    ],
)
def test_reject_invalid_or_oversized_upload(filename, content_type, content, message):
    with pytest.raises(ValueError, match=message):
        extract_uploaded_document(filename, content_type, content)


def test_reject_oversized_upload():
    with pytest.raises(ValueError, match="10 MB"):
        extract_uploaded_document("document.pdf", "application/pdf", OversizedContent())


def test_reject_empty_workbook_and_extract_multiple_startup_rows():
    empty_workbook = make_xlsx([("Empty", [])])
    with pytest.raises(ValueError, match="No supported startup fields"):
        extract_uploaded_document(
            "empty.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            empty_workbook,
        )

    multiple_rows = make_xlsx([
        ("Startups", [["Startup Name", "Funding Amount"], ["Northstar", 100], ["Southstar", 200]])
    ])
    result = extract_uploaded_document(
        "multiple.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        multiple_rows,
    )
    assert [record["startup_name"] for record in result["records"]] == ["Northstar", "Southstar"]

    repeated_names = make_xlsx([
        ("Startups", [["Startup Name", "Number of Founders"], ["Same Company", 2], ["Same Company", 4]])
    ])
    result = extract_uploaded_document(
        "repeated-names.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        repeated_names,
    )
    assert [record["number_of_founders"] for record in result["records"]] == [2, 4]


@pytest.fixture
def prediction_client(monkeypatch):
    import app as root_app

    root_app.app.config["TESTING"] = True
    client = root_app.app.test_client()
    with client.session_transaction() as session:
        session["user"] = "document-test@example.com"
    monkeypatch.setattr(root_app, "save_prediction_history", lambda *_args, **_kwargs: "test-id")
    monkeypatch.setattr(root_app.ml_predictor, "load_model", lambda: (
        SimpleNamespace(feature_importances_=[1 / len(MODEL_FEATURES)] * len(MODEL_FEATURES)),
        model_metadata(),
    ))
    monkeypatch.setattr(root_app.ml_predictor, "batch_predict", lambda inputs: [
        {
            "prediction": "Success",
            "success_probability": 70.0,
            "failure_probability": 30.0,
            "confidence": 70.0,
        }
        for _ in inputs
    ])
    return root_app, client


def test_pdf_upload_returns_editable_model_feature_preview(prediction_client):
    root_app, client = prediction_client
    record = make_startup_record()
    pdf = make_pdf([[f"{field.replace('_', ' ')}: {value}" for field, value in record.items()]])
    response = client.post("/api/ml-predict", data={
        "preview_only": "1",
        "document": (BytesIO(pdf), "startup.pdf", "application/pdf"),
    })

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["preview"][0]["values"]["founder_experience"] == 5.0
    assert payload["preview"][0]["issues"] == []
    assert {field["name"] for field in payload["fields"]} == set(MODEL_FEATURES)


def test_xlsx_upload_previews_multiple_records_and_uses_real_batch_pipeline(prediction_client, monkeypatch):
    root_app, client = prediction_client
    content = workbook_for_records([
        make_startup_record("Northstar"),
        make_startup_record("Southstar", city="Austin", market_size="Medium"),
    ])
    preview_response = client.post("/api/ml-predict", data={
        "preview_only": "1",
        "document": (
            BytesIO(content),
            "startups.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    })
    assert preview_response.status_code == 200, preview_response.get_json()
    preview = preview_response.get_json()["preview"]
    assert len(preview) == 2
    assert preview[1]["values"]["startup_name"] == "Southstar"

    received = {}
    def fake_batch_predict(inputs):
        received["inputs"] = inputs
        return [
            {"prediction": "Success", "success_probability": 70, "failure_probability": 30, "confidence": 70},
            {"prediction": "Failure", "success_probability": 20, "failure_probability": 80, "confidence": 80},
        ]

    monkeypatch.setattr(root_app.ml_predictor, "batch_predict", fake_batch_predict)
    response = client.post("/api/ml-predict", json={
        "document_records": [item["values"] for item in preview],
    })

    assert response.status_code == 200
    assert [item["prediction"] for item in response.get_json()["document_results"]] == ["Success", "Failure"]
    assert [item["startup_name"] for item in response.get_json()["document_results"]] == ["Northstar", "Southstar"]
    assert response.get_json()["document_results"][0]["success_probability"] == 70
    assert response.get_json()["probability_available"] is True
    assert len(response.get_json()["feature_importance"]) == len(MODEL_FEATURES)
    assert sum(item["value"] for item in response.get_json()["feature_importance"]) == pytest.approx(100)
    assert received["inputs"][0]["city"] == 1
    assert received["inputs"][0]["market_size"] == 0
    assert received["inputs"][0]["industry"] == "Technology"


def test_preview_reports_missing_fields_and_category_correction(prediction_client):
    _, client = prediction_client
    partial = make_startup_record(city="Atlantis")
    partial.pop("burn_rate")
    response = client.post("/api/ml-predict", json={"document_records": [partial]})
    assert response.status_code == 400
    issues = response.get_json()["validation_issues"]
    assert {issue["field"] for issue in issues} == {"burn_rate", "city"}
    assert any("supported categories" in issue["message"] for issue in issues)

    invalid_number = make_startup_record(burn_rate="not numeric")
    response = client.post("/api/ml-predict", json={"document_records": [invalid_number]})
    assert response.status_code == 400
    assert response.get_json()["validation_issues"][0]["field"] == "burn_rate"


def test_preview_and_validation_do_not_use_the_success_label(prediction_client):
    _, client = prediction_client
    record = make_startup_record()
    record["success"] = "Success"
    response = client.post("/api/ml-predict", json={"document_records": [record]})
    assert response.status_code == 200
    assert response.get_json()["document_results"][0]["prediction"] == "Success"


def test_actual_trained_model_predicts_complete_uploaded_record():
    from pathlib import Path
    import app as root_app

    if not Path("models/startup_model.pkl").exists() or not Path("models/preprocessing_info.pkl").exists():
        pytest.skip("Trained model artifacts are unavailable in this checkout.")
    root_app.app.config["TESTING"] = True
    client = root_app.app.test_client()
    with client.session_transaction() as session:
        session["user"] = "real-model-upload-test@example.com"
    response = client.post("/api/ml-predict", json={
        "document_records": [make_startup_record()],
    })
    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["document_results"][0]["prediction"] in {"Success", "Failure"}
    assert payload["probability_available"] is True
    assert 0 <= payload["document_results"][0]["success_probability"] <= 100
    assert 0 <= payload["document_results"][0]["failure_probability"] <= 100
    assert len(payload["feature_importance"]) == len(MODEL_FEATURES)
    assert sum(item["value"] for item in payload["feature_importance"]) == pytest.approx(100)


def test_manual_json_prediction_contract_is_unchanged(prediction_client, monkeypatch):
    root_app, client = prediction_client
    monkeypatch.setattr(root_app, "predict_startup_success", lambda *args: (75, "Success", {}, []))
    monkeypatch.setattr(root_app, "generate_recommendations", lambda *_args: [])
    response = client.post("/predict", json={
        "funding_amount": 10,
        "employees": 1,
        "industry": "Retail",
        "revenue": 20,
        "location": "Austin",
    })
    assert response.status_code == 200
    assert set(response.get_json()) == {
        "probability", "result", "scores", "feature_importance", "recommendations", "prediction_id"
    }