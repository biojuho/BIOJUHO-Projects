import sys

import requests

# WIN FIX
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8001"


def test_upload_flow():
    print("🚀 Starting API Integration Test (QA Check)...")

    # 1. Create Dummy PDF
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Kids [3 0 R]\n/Count 1\n/Type /Pages\n>>\nendobj\n3 0 obj\n<<\n/MediaBox [0 0 595 842]\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/F1 4 0 R\n>>\n>>\n/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\n5 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 24 Tf\n100 100 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\n0000000256 00000 n\n0000000343 00000 n\ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n438\n%%EOF"

    files = {"file": ("test.pdf", pdf_content, "application/pdf")}
    data = {"title": "QA Test Paper", "abstract": "This is a test paper for QA verification."}

    headers = {"Authorization": "Bearer test-token-bypass"}

    print(f"📤 Uploading PDF to {BASE_URL}/upload ...")

    try:
        response = requests.post(f"{BASE_URL}/upload", files=files, data=data, headers=headers)

        if response.status_code == 200:
            print("✅ Upload Success!")
            result = response.json()
            print(f"   CID: {result.get('cid')}")
            print(f"   Analysis Status: {result.get('analysis', {}).get('status')}")

            # Verify Analysis Data
            if result.get("analysis", {}).get("status") == "indexed":
                print("✅ Vector Indexing Confirmed")
            else:
                print("⚠️ Analysis status is not 'indexed'")

            return True
        else:
            print(f"❌ Upload Failed: {response.status_code}")
            print(response.text)
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Connection Failed. Is the backend running on port 8000?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_upload_flow()
