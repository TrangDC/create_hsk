# services/image_gen_logger.py
"""
Logger theo dõi số request và token khi sinh ảnh flashcard Tiếng Anh.
Sau khi hoàn tất session, tự động ghi file JSON + upload lên Google Drive.
"""

import os
import json
import base64
import mimetypes
import socket
import platform
import getpass
import requests
from datetime import datetime


# URL Google Apps Script Web App (dùng chung với upload_drive.py)
WEB_APP_URL = 'https://script.google.com/macros/s/AKfycbxLIxvKSHtLY57wPss-K6LrKnV5s-abX166HEXs-cPY7DSivfZnw0-ct2luvV-wzQk9Xg/exec'

# Thư mục lưu log cục bộ
LOG_DIR = "output/logs"


class ImageGenLogger:
    """
    Thu thập thống kê từng request sinh ảnh và upload log lên Drive khi xong.

    Cách dùng:
        logger = ImageGenLogger(session_name="eng_flashcard_Animals")
        logger.log_request(word="cat", status="success", tokens_in=120, tokens_out=0, attempts=1)
        logger.log_request(word="dog", status="failed", error="Empty response", attempts=3)
        logger.finish_and_upload()
    """

    def __init__(self, session_name: str):
        self.session_name = session_name
        self.start_time = datetime.now()
        self.records: list[dict] = []
        self.machine_info = self._get_machine_info()

    @staticmethod
    def _get_machine_info() -> dict:
        """Thu thập thông tin máy đang chạy tool."""
        try:
            return {
                "hostname": socket.gethostname(),
                "user":     getpass.getuser(),
                "os":       platform.system(),
                "os_version": platform.version(),
            }
        except Exception:
            return {"hostname": "unknown", "user": "unknown", "os": "unknown", "os_version": "unknown"}

    # ------------------------------------------------------------------
    # Ghi nhận từng request
    # ------------------------------------------------------------------
    def log_request(
        self,
        word: str,
        status: str,          # "success" | "skipped" | "failed"
        tokens_in: int = 0,
        tokens_out: int = 0,
        total_tokens: int = 0,
        attempts: int = 1,
        error: str | None = None,
    ):
        self.records.append({
            "word": word,
            "status": status,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": total_tokens,
            "attempts": attempts,
            "error": error,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })

    # ------------------------------------------------------------------
    # Tổng hợp
    # ------------------------------------------------------------------
    def get_summary(self) -> dict:
        duration = (datetime.now() - self.start_time).total_seconds()
        success_records  = [r for r in self.records if r["status"] == "success"]
        failed_records   = [r for r in self.records if r["status"] == "failed"]
        skipped_records  = [r for r in self.records if r["status"] == "skipped"]

        total_tokens_in  = sum(r["tokens_in"]    for r in self.records)
        total_tokens_out = sum(r["tokens_out"]   for r in self.records)
        total_tokens     = sum(r["total_tokens"] for r in self.records)
        total_attempts   = sum(r["attempts"]     for r in self.records)

        return {
            "session_name":       self.session_name,
            "machine":            self.machine_info,
            "start_time":         self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds":   round(duration, 1),
            "total_words":        len(self.records),
            "total_requests":     len(success_records) + len(failed_records),  # không tính skipped
            "success":            len(success_records),
            "failed":             len(failed_records),
            "skipped":            len(skipped_records),
            "total_attempts":     total_attempts,   # bao gồm cả retry
            "total_tokens_in":    total_tokens_in,
            "total_tokens_out":   total_tokens_out,
            "total_tokens":       total_tokens,
            "details":            self.records,
        }

    # ------------------------------------------------------------------
    # In tóm tắt ra console
    # ------------------------------------------------------------------
    def print_summary(self):
        s = self.get_summary()
        print("\n" + "=" * 55)
        print(f"📊 LOG TỔNG KẾT: {s['session_name']}")
        print("=" * 55)
        m = s['machine']
        print(f"  💻 Máy           : {m['hostname']} ({m['user']})")
        print(f"  🖥  Hệ điều hành  : {m['os']} {m['os_version']}")
        print(f"  ⏱  Thời gian chạy : {s['duration_seconds']}s")
        print(f"  📋 Tổng từ vựng   : {s['total_words']}")
        print(f"  🚀 Tổng request   : {s['total_requests']}  (retry: {s['total_attempts'] - s['total_requests']})")
        print(f"  ✅ Thành công     : {s['success']}")
        print(f"  ❌ Thất bại       : {s['failed']}")
        print(f"  ⏭  Bỏ qua        : {s['skipped']}")
        print(f"  🔢 Token input    : {s['total_tokens_in']}")
        print(f"  🔢 Token output   : {s['total_tokens_out']}")
        print(f"  🔢 Token tổng     : {s['total_tokens']}")
        print("=" * 55)

    # ------------------------------------------------------------------
    # Lưu file JSON cục bộ
    # ------------------------------------------------------------------
    def save_local(self) -> str:
        """Ghi log ra file JSON, trả về đường dẫn file."""
        os.makedirs(LOG_DIR, exist_ok=True)
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.session_name)
        file_name = f"log_{safe_name}_{timestamp}.json"
        file_path = os.path.join(LOG_DIR, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.get_summary(), f, ensure_ascii=False, indent=2)

        print(f"💾 Đã lưu log cục bộ: {file_path}")
        return file_path

    # ------------------------------------------------------------------
    # Upload lên Drive qua Google Apps Script
    # ------------------------------------------------------------------
    def upload_to_drive(self, file_path: str) -> bool:
        """Upload file JSON lên Drive. Trả về True nếu thành công."""
        if not os.path.exists(file_path):
            print(f"⚠️ Không tìm thấy file log để upload: {file_path}")
            return False

        file_name = os.path.basename(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/json"

        with open(file_path, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "fileName": file_name,
            "mimeType": mime_type,
            "fileData": base64_data,
        }

        try:
            print(f"☁️  Đang upload log lên Drive: {file_name} ...")
            response = requests.post(WEB_APP_URL, json=payload, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    print(f"✅ Upload log thành công!")
                    print(f"   🔗 Link: {result.get('url', 'N/A')}")
                    return True
                else:
                    print(f"❌ Apps Script lỗi: {result.get('message')}")
            else:
                print(f"❌ HTTP {response.status_code}: {response.text[:200]}")

        except requests.exceptions.Timeout:
            print("⚠️ Upload log timeout — log đã được lưu cục bộ.")
        except Exception as e:
            print(f"⚠️ Lỗi upload log: {e}")

        return False

    # ------------------------------------------------------------------
    # Hàm tiện ích: lưu + upload một lần
    # ------------------------------------------------------------------
    def finish_and_upload(self):
        """In tóm tắt, lưu file JSON cục bộ, rồi upload lên Drive."""
        self.print_summary()
        file_path = self.save_local()
        self.upload_to_drive(file_path)
