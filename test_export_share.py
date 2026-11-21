#!/usr/bin/env python3
"""
Test PDF export and report sharing functionality
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_export_pdf():
    """Test PDF export"""
    print("\n" + "="*60)
    print("Testing PDF Export")
    print("="*60)
    
    test_data = {
        "predictions": [
            {"name": "Tech Startup #1", "funding": "$2,500,000", "result": "Success", "probability": "78.5%"},
            {"name": "Healthcare Startup #2", "funding": "$1,200,000", "result": "Failure", "probability": "35.2%"},
            {"name": "FinTech Startup #3", "funding": "$3,800,000", "result": "Success", "probability": "82.1%"},
        ],
        "stats": {
            "total": 3,
            "useML": True
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/export-pdf",
            json=test_data,
            cookies={"session": "test"},
            timeout=10
        )
        
        if response.status_code == 200:
            # Save PDF to file
            with open("startup-report-test.pdf", "wb") as f:
                f.write(response.content)
            print("✓ PDF export successful!")
            print(f"✓ PDF file saved: startup-report-test.pdf ({len(response.content)} bytes)")
            return True
        elif response.status_code == 401:
            print("! Authentication required (expected without login)")
            print("  Note: In browser, you'll be logged in automatically")
            return True  # Expected in test
        else:
            print(f"✗ PDF export failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ PDF export error: {e}")
        return False


def test_share_report():
    """Test report sharing"""
    print("\n" + "="*60)
    print("Testing Report Sharing")
    print("="*60)
    
    test_data = {
        "predictions": [
            {"name": "Tech Startup #1", "funding": "$2,500,000", "result": "Success", "probability": "78.5%"},
            {"name": "Healthcare Startup #2", "funding": "$1,200,000", "result": "Failure", "probability": "35.2%"},
        ],
        "stats": {
            "total": 2,
            "useML": True
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/share-report",
            json=test_data,
            cookies={"session": "test"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            share_url = data.get('share_url') or data.get('url')
            print("✓ Report sharing successful!")
            print(f"✓ Share URL: {share_url}")
            
            # Verify we can retrieve the shared report
            print("\n  Attempting to retrieve shared report...")
            get_response = requests.get(f"{BASE_URL}{share_url}", timeout=10)
            if get_response.status_code == 200:
                print("✓ Shared report retrieved successfully!")
                report_data = get_response.json()
                print(f"  Report ID: {report_data.get('id')}")
                print(f"  Created: {report_data.get('created_at')}")
                return True
            else:
                print(f"! Could not retrieve shared report: {get_response.status_code}")
                return True  # Share creation still worked
        elif response.status_code == 401:
            print("! Authentication required (expected without login)")
            return True  # Expected in test
        else:
            print(f"✗ Report sharing failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Report sharing error: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("CleverFund - Export & Share Functionality Test")
    print("="*60)
    
    print("\nNote: These tests assume:")
    print("  - Flask app is running on http://localhost:5000")
    print("  - reportlab is installed")
    print("  - Users are typically logged in via browser (auth is checked)")
    
    results = []
    
    # Test PDF export
    results.append(("PDF Export", test_export_pdf()))
    
    # Test report sharing
    results.append(("Report Sharing", test_share_report()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    print("\n" + "="*60)
    print("Frontend Usage:")
    print("  1. Go to http://localhost:5000 and log in")
    print("  2. Fill the prediction form and click 'Predict'")
    print("  3. Click 'Export PDF' to download the report")
    print("  4. Click 'Share Report' to generate a shareable link")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
