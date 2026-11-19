"""
PDF Editor - PDFファイルの分割・回転・JPEG変換を行うGUIツール

作者: Claude
日付: 2025年7月21日
"""

import os
import sys
import platform
import logging
import threading
import subprocess
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime

try:
    from PyPDF2 import PdfReader, PdfWriter
    PDF_AVAILABLE = True
except ImportError:
    try:
        from pypdf import PdfReader, PdfWriter
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

SCRIPT_DIR = Path(__file__).resolve().parent
APP_VERSION = "2025年7月21日バージョン"
APP_TITLE = "PDF Editor - 分割・回転・JPEG変換"

# ============================================================================
# ログ設定
# ============================================================================

log_file_path = SCRIPT_DIR / "pdf-editor.log"

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file_path, encoding="utf-8", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
logger.info("=" * 50)
logger.info("PDF Editor 開始")
logger.info(f"ログファイル: {log_file_path}")
logger.info(f"Python: {sys.version}")
logger.info(f"PDFライブラリ: {'有効' if PDF_AVAILABLE else '無効'}")
logger.info(f"pdf2image: {'有効' if PDF2IMAGE_AVAILABLE else '無効'}")
logger.info("=" * 50)


# ============================================================================
# Poppler 検出
# ============================================================================

def find_poppler_path():
    """pdf2image 用の Poppler bin ディレクトリを探す。見つからなければ None。"""
    env = os.environ.get("POPPLER_PATH", "").strip()
    if env and Path(env).is_dir():
        return env

    system = platform.system()
    if system == "Windows":
        possible_paths = [
            r"C:\Program Files\poppler\Library\bin",
            r"C:\Program Files\Poppler\Library\bin",
            r"C:\Program Files\Poppler\bin",
            r"C:\Program Files (x86)\Poppler\bin",
            r"C:\poppler-24.08.0\Library\bin",
            r"C:\poppler\Library\bin",
        ]
        exe_name = "pdftoppm.exe"
    else:
        possible_paths = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
        ]
        exe_name = "pdftoppm"

    for path in possible_paths:
        if Path(path, exe_name).is_file():
            logger.info(f"Poppler を検出: {path}")
            return path

    which = shutil.which(exe_name)
    if which:
        logger.info(f"Poppler を PATH から検出: {Path(which).parent}")
        return str(Path(which).parent)

    try:
        result = subprocess.run(
            [exe_name, "-v"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            logger.info("Poppler がシステム PATH で利用可能です")
            return ""
    except Exception:
        pass

    logger.warning("Poppler が見つかりませんでした（JPEG変換に必要）")
    return None


# ============================================================================
# ページ範囲パース
# ============================================================================

def parse_page_ranges(text, total_pages):
    """
    「1-3,5,8-10」形式の文字列を1始まりのページ番号リストに変換する。
    戻り値: ソート済み・重複なしのページ番号リスト（1始まり）
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("ページ範囲が空です")

    pages = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            start = int(left.strip())
            end = int(right.strip())
            if start > end:
                start, end = end, start
            if start < 1 or end > total_pages:
                raise ValueError(
                    f"ページ範囲 {start}-{end} が無効です（総ページ数: {total_pages}）"
                )
            pages.update(range(start, end + 1))
        else:
            page = int(part)
            if page < 1 or page > total_pages:
                raise ValueError(
                    f"ページ番号 {page} が無効です（総ページ数: {total_pages}）"
                )
            pages.add(page)

    if not pages:
        raise ValueError("有効なページ番号がありません")
    return sorted(pages)


def unique_output_path(directory, filename):
    """同名ファイルがある場合は連番を付与して一意なパスを返す。"""
    path = Path(directory) / filename
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = Path(directory) / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


# ============================================================================
# PDF操作
# ============================================================================

class PDFOperations:
    """PDFの分割・回転・JPEG変換処理をまとめたクラス。"""

    @staticmethod
    def get_page_count(pdf_path):
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            return len(reader.pages)

    @staticmethod
    def split_every_n_pages(pdf_path, output_dir, pages_per_file=1, prefix=None):
        """Nページごとに分割して保存する。"""
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = prefix or pdf_path.stem
        created = []

        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            total = len(reader.pages)
            if total == 0:
                raise ValueError("PDFにページがありません")

            chunk = max(1, int(pages_per_file))
            part = 1
            for start in range(0, total, chunk):
                writer = PdfWriter()
                end = min(start + chunk, total)
                for i in range(start, end):
                    writer.add_page(reader.pages[i])

                if chunk == 1:
                    name = f"{prefix}_page_{start + 1:03d}.pdf"
                else:
                    name = f"{prefix}_part_{part:03d}_p{start + 1:03d}-{end:03d}.pdf"
                out = unique_output_path(output_dir, name)
                with open(out, "wb") as out_f:
                    writer.write(out_f)
                created.append(out)
                part += 1

        return created

    @staticmethod
    def split_by_ranges(pdf_path, output_dir, ranges_text, prefix=None):
        """
        カンマ区切りの範囲ごとに1ファイルずつ出力する。
        例: 「1-3,5,8-10」→ 3ファイル
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = prefix or pdf_path.stem
        created = []

        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            total = len(reader.pages)
            if total == 0:
                raise ValueError("PDFにページがありません")

            parts = [p.strip() for p in ranges_text.split(",") if p.strip()]
            if not parts:
                raise ValueError("ページ範囲が空です")

            for idx, part in enumerate(parts, start=1):
                pages = parse_page_ranges(part, total)
                writer = PdfWriter()
                for page_num in pages:
                    writer.add_page(reader.pages[page_num - 1])

                if len(pages) == 1:
                    label = f"p{pages[0]:03d}"
                else:
                    label = f"p{pages[0]:03d}-{pages[-1]:03d}"
                name = f"{prefix}_range_{idx:02d}_{label}.pdf"
                out = unique_output_path(output_dir, name)
                with open(out, "wb") as out_f:
                    writer.write(out_f)
                created.append(out)

        return created

    @staticmethod
    def extract_pages(pdf_path, output_path, pages):
        """指定ページだけを1つのPDFとして抽出する。"""
        pdf_path = Path(pdf_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            total = len(reader.pages)
            writer = PdfWriter()
            for page_num in pages:
                if page_num < 1 or page_num > total:
                    raise ValueError(f"ページ番号 {page_num} が無効です")
                writer.add_page(reader.pages[page_num - 1])
            with open(output_path, "wb") as out_f:
                writer.write(out_f)
        return output_path

    @staticmethod
    def rotate_pages(pdf_path, output_path, angle, page_numbers=None):
        """
        指定ページ（または全ページ）を回転して新しいPDFを保存する。
        angle: 90 / 180 / 270（時計回り）
        page_numbers: 1始まりのリスト。Noneなら全ページ。
        """
        if angle not in (90, 180, 270, -90, -180, -270):
            raise ValueError("回転角度は 90 / 180 / 270 のいずれかです")

        # 正規化（負の角度を正に）
        angle = angle % 360
        if angle == 0:
            raise ValueError("回転角度が0です")

        pdf_path = Path(pdf_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            total = len(reader.pages)
            targets = set(page_numbers) if page_numbers else set(range(1, total + 1))

            for p in targets:
                if p < 1 or p > total:
                    raise ValueError(f"ページ番号 {p} が無効です（総ページ数: {total}）")

            writer = PdfWriter()
            for i in range(total):
                page = reader.pages[i]
                if (i + 1) in targets:
                    page.rotate(angle)
                writer.add_page(page)

            with open(output_path, "wb") as out_f:
                writer.write(out_f)

        return output_path

    @staticmethod
    def convert_to_jpeg(
        pdf_path,
        output_dir,
        dpi=150,
        quality=85,
        page_numbers=None,
        poppler_path=None,
        prefix=None,
    ):
        """
        PDFの各ページをJPEG画像として保存する。
        page_numbers: 1始まりのリスト。Noneなら全ページ。
        戻り値: 作成したJPEGパスのリスト
        """
        if not PDF2IMAGE_AVAILABLE:
            raise RuntimeError(
                "pdf2image がインストールされていません。\npip install pdf2image"
            )

        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        prefix = prefix or pdf_path.stem

        dpi = max(72, int(dpi))
        quality = max(1, min(95, int(quality)))

        base_kwargs = {
            "dpi": dpi,
            "fmt": "jpeg",
            "jpegopt": {"quality": quality, "optimize": True},
            "thread_count": 2,
        }
        if poppler_path:
            base_kwargs["poppler_path"] = poppler_path

        # 連続ページはまとめて変換し、飛び番は範囲を分けて処理する
        if page_numbers:
            pages = sorted(set(page_numbers))
            ranges = []
            start = prev = pages[0]
            for p in pages[1:]:
                if p == prev + 1:
                    prev = p
                else:
                    ranges.append((start, prev))
                    start = prev = p
            ranges.append((start, prev))
        else:
            ranges = [(None, None)]

        created = []
        try:
            for first_page, last_page in ranges:
                kwargs = dict(base_kwargs)
                if first_page is not None:
                    kwargs["first_page"] = first_page
                    kwargs["last_page"] = last_page
                    page_start = first_page
                else:
                    page_start = 1

                images = convert_from_path(str(pdf_path), **kwargs)
                for offset, image in enumerate(images):
                    page_num = page_start + offset
                    name = f"{prefix}_page_{page_num:03d}.jpg"
                    out = unique_output_path(output_dir, name)
                    image.save(
                        str(out),
                        "JPEG",
                        quality=quality,
                        optimize=True,
                        progressive=True,
                    )
                    created.append(out)
        except PDFInfoNotInstalledError as e:
            raise RuntimeError(
                "Poppler が見つかりません。\n"
                "Windows: Poppler for Windows をインストールし、\n"
                "環境変数 POPPLER_PATH に bin フォルダを設定してください。\n"
                f"詳細: {e}"
            ) from e

        if not created:
            raise ValueError("JPEG画像が1枚も作成されませんでした")
        return created


# ============================================================================
# GUI
# ============================================================================

class PDFEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} ({APP_VERSION})")
        self.root.geometry("720x700")
        self.root.minsize(640, 600)

        self.pdf_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.page_count = tk.IntVar(value=0)
        self.split_mode = tk.StringVar(value="every")  # every / ranges / extract
        self.pages_per_file = tk.StringVar(value="1")
        self.range_text = tk.StringVar(value="")
        self.rotate_target = tk.StringVar(value="all")  # all / selected
        self.rotate_pages_text = tk.StringVar(value="")
        self.rotate_angle = tk.IntVar(value=90)
        self.jpeg_target = tk.StringVar(value="all")  # all / selected
        self.jpeg_pages_text = tk.StringVar(value="")
        self.jpeg_dpi = tk.StringVar(value="150")
        self.jpeg_quality = tk.StringVar(value="85")
        self.is_processing = False
        self.poppler_path = find_poppler_path()

        if not PDF_AVAILABLE:
            messagebox.showerror(
                "ライブラリ不足",
                "PyPDF2（または pypdf）がインストールされていません。\n\n"
                "pip install PyPDF2\n\n"
                "を実行してから再起動してください。",
            )

        self._build_ui()
        self.root.after(10, self._center_window)
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width() or 720
        h = self.root.winfo_height() or 700
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = max(0, (sh - h) // 2 - 40)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        # --- ファイル選択 ---
        file_frame = ttk.LabelFrame(main, text="PDFファイル", padding=10)
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="入力:").grid(row=0, column=0, sticky="w")
        ttk.Entry(file_frame, textvariable=self.pdf_path).grid(
            row=0, column=1, sticky="ew", padx=6
        )
        ttk.Button(file_frame, text="参照", width=10, command=self._select_pdf).grid(
            row=0, column=2
        )

        ttk.Label(file_frame, text="出力先:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(file_frame, textvariable=self.output_dir).grid(
            row=1, column=1, sticky="ew", padx=6, pady=(6, 0)
        )
        ttk.Button(file_frame, text="参照", width=10, command=self._select_output).grid(
            row=1, column=2, pady=(6, 0)
        )

        info = ttk.Frame(file_frame)
        info.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(info, text="ページ数:").pack(side=tk.LEFT)
        ttk.Label(info, textvariable=self.page_count, width=6).pack(side=tk.LEFT)
        ttk.Button(info, text="情報を更新", command=self._refresh_info).pack(
            side=tk.LEFT, padx=(12, 0)
        )

        # --- ノートブック（分割 / 回転 / JPEG変換） ---
        notebook = ttk.Notebook(main)
        notebook.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        split_tab = ttk.Frame(notebook, padding=10)
        rotate_tab = ttk.Frame(notebook, padding=10)
        jpeg_tab = ttk.Frame(notebook, padding=10)
        notebook.add(split_tab, text="分割")
        notebook.add(rotate_tab, text="回転")
        notebook.add(jpeg_tab, text="JPEG変換")

        self._build_split_tab(split_tab)
        self._build_rotate_tab(rotate_tab)
        self._build_jpeg_tab(jpeg_tab)

        # --- 実行ボタン ---
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        self.split_btn = ttk.Button(
            btn_frame, text="分割を実行", command=self._run_split, width=14
        )
        self.split_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.rotate_btn = ttk.Button(
            btn_frame, text="回転を実行", command=self._run_rotate, width=14
        )
        self.rotate_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.jpeg_btn = ttk.Button(
            btn_frame, text="JPEG変換を実行", command=self._run_jpeg, width=16
        )
        self.jpeg_btn.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(btn_frame, text="出力先を開く", command=self._open_output_dir, width=12).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(btn_frame, text="終了", command=self._on_closing, width=8).pack(
            side=tk.RIGHT
        )

        # --- 進捗 ---
        self.progress = ttk.Progressbar(main, mode="indeterminate")
        self.progress.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        # --- ログ ---
        log_frame = ttk.LabelFrame(main, text="ログ", padding=8)
        log_frame.grid(row=4, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, wrap=tk.WORD, state="disabled"
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        if not PDF_AVAILABLE:
            self._log("警告: PyPDF2 / pypdf が見つかりません。pip install PyPDF2 を実行してください。")
            self.split_btn.config(state="disabled")
            self.rotate_btn.config(state="disabled")
        else:
            self._log("PDFファイルを選択してください。")

        if not PDF2IMAGE_AVAILABLE:
            self._log("警告: pdf2image が見つかりません。pip install pdf2image を実行してください。")
            self.jpeg_btn.config(state="disabled")
        elif self.poppler_path is None:
            self._log(
                "警告: Poppler が見つかりません。JPEG変換には Poppler が必要です。"
                " 環境変数 POPPLER_PATH に bin フォルダを設定してください。"
            )
        else:
            poppler_desc = self.poppler_path or "(システム PATH)"
            self._log(f"Poppler: {poppler_desc}")

    def _build_split_tab(self, parent):
        parent.columnconfigure(0, weight=1)

        ttk.Radiobutton(
            parent,
            text="Nページごとに分割（1なら1ページずつ）",
            variable=self.split_mode,
            value="every",
            command=self._update_split_ui,
        ).grid(row=0, column=0, sticky="w")

        every_row = ttk.Frame(parent)
        every_row.grid(row=1, column=0, sticky="w", padx=(24, 0), pady=(2, 8))
        ttk.Label(every_row, text="ページ数:").pack(side=tk.LEFT)
        self.pages_per_file_entry = ttk.Entry(
            every_row, textvariable=self.pages_per_file, width=6
        )
        self.pages_per_file_entry.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Radiobutton(
            parent,
            text="範囲ごとに分割（例: 1-3,5,8-10 → 各範囲が別ファイル）",
            variable=self.split_mode,
            value="ranges",
            command=self._update_split_ui,
        ).grid(row=2, column=0, sticky="w")

        ranges_row = ttk.Frame(parent)
        ranges_row.grid(row=3, column=0, sticky="ew", padx=(24, 0), pady=(2, 8))
        ranges_row.columnconfigure(1, weight=1)
        ttk.Label(ranges_row, text="範囲:").grid(row=0, column=0, sticky="w")
        self.range_entry = ttk.Entry(ranges_row, textvariable=self.range_text)
        self.range_entry.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        ttk.Radiobutton(
            parent,
            text="指定ページを1つのPDFに抽出（例: 2,4-6）",
            variable=self.split_mode,
            value="extract",
            command=self._update_split_ui,
        ).grid(row=4, column=0, sticky="w")

        extract_hint = ttk.Label(
            parent,
            text="※ 抽出モードでは上の「範囲」欄の指定を使用します",
            foreground="gray",
        )
        extract_hint.grid(row=5, column=0, sticky="w", padx=(24, 0), pady=(2, 0))

        self._update_split_ui()

    def _build_rotate_tab(self, parent):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="対象:").grid(row=0, column=0, sticky="w")
        target_frame = ttk.Frame(parent)
        target_frame.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(
            target_frame,
            text="全ページ",
            variable=self.rotate_target,
            value="all",
            command=self._update_rotate_ui,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            target_frame,
            text="指定ページ",
            variable=self.rotate_target,
            value="selected",
            command=self._update_rotate_ui,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(parent, text="ページ:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.rotate_pages_entry = ttk.Entry(parent, textvariable=self.rotate_pages_text)
        self.rotate_pages_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0), padx=(6, 0))
        ttk.Label(parent, text="例: 1,3-5", foreground="gray").grid(
            row=2, column=1, sticky="w", padx=(6, 0)
        )

        ttk.Label(parent, text="角度:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        angle_frame = ttk.Frame(parent)
        angle_frame.grid(row=3, column=1, sticky="w", pady=(8, 0))
        for label, value in (("時計回り 90°", 90), ("180°", 180), ("時計回り 270°", 270)):
            ttk.Radiobutton(
                angle_frame, text=label, variable=self.rotate_angle, value=value
            ).pack(side=tk.LEFT, padx=(0, 12))

        self._update_rotate_ui()

    def _build_jpeg_tab(self, parent):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="対象:").grid(row=0, column=0, sticky="w")
        target_frame = ttk.Frame(parent)
        target_frame.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(
            target_frame,
            text="全ページ",
            variable=self.jpeg_target,
            value="all",
            command=self._update_jpeg_ui,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            target_frame,
            text="指定ページ",
            variable=self.jpeg_target,
            value="selected",
            command=self._update_jpeg_ui,
        ).pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(parent, text="ページ:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.jpeg_pages_entry = ttk.Entry(parent, textvariable=self.jpeg_pages_text)
        self.jpeg_pages_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0), padx=(6, 0))
        ttk.Label(parent, text="例: 1,3-5", foreground="gray").grid(
            row=2, column=1, sticky="w", padx=(6, 0)
        )

        ttk.Label(parent, text="解像度:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        dpi_row = ttk.Frame(parent)
        dpi_row.grid(row=3, column=1, sticky="w", pady=(8, 0), padx=(6, 0))
        self.jpeg_dpi_entry = ttk.Entry(dpi_row, textvariable=self.jpeg_dpi, width=8)
        self.jpeg_dpi_entry.pack(side=tk.LEFT)
        ttk.Label(dpi_row, text="DPI（72〜300推奨）", foreground="gray").pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Label(parent, text="画質:").grid(row=4, column=0, sticky="w", pady=(8, 0))
        quality_row = ttk.Frame(parent)
        quality_row.grid(row=4, column=1, sticky="w", pady=(8, 0), padx=(6, 0))
        self.jpeg_quality_entry = ttk.Entry(
            quality_row, textvariable=self.jpeg_quality, width=8
        )
        self.jpeg_quality_entry.pack(side=tk.LEFT)
        ttk.Label(quality_row, text="1〜95（高いほど高画質・大容量）", foreground="gray").pack(
            side=tk.LEFT, padx=(8, 0)
        )

        ttk.Label(
            parent,
            text="※ 出力ファイル名: 元ファイル名_page_001.jpg …",
            foreground="gray",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._update_jpeg_ui()

    def _update_split_ui(self):
        mode = self.split_mode.get()
        self.pages_per_file_entry.config(state="normal" if mode == "every" else "disabled")
        self.range_entry.config(
            state="normal" if mode in ("ranges", "extract") else "disabled"
        )

    def _update_rotate_ui(self):
        state = "normal" if self.rotate_target.get() == "selected" else "disabled"
        self.rotate_pages_entry.config(state=state)

    def _update_jpeg_ui(self):
        state = "normal" if self.jpeg_target.get() == "selected" else "disabled"
        self.jpeg_pages_entry.config(state=state)

    # ------------------------------------------------------------------
    # ログ / UI補助
    # ------------------------------------------------------------------

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}\n"
        logger.info(message)

        def append():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, line)
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")

        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self.root.after(0, append)

    def _set_busy(self, busy):
        self.is_processing = busy

        def apply():
            state = "disabled" if busy else "normal"
            if PDF_AVAILABLE:
                self.split_btn.config(state=state)
                self.rotate_btn.config(state=state)
            if PDF2IMAGE_AVAILABLE and self.poppler_path is not None:
                self.jpeg_btn.config(state=state)
            elif not busy and PDF2IMAGE_AVAILABLE and self.poppler_path is None:
                # Poppler 未検出時は常に無効のまま
                self.jpeg_btn.config(state="disabled")
            if busy:
                self.progress.start(12)
            else:
                self.progress.stop()

        self.root.after(0, apply)

    def _select_pdf(self):
        path = filedialog.askopenfilename(
            title="PDFファイルを選択",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        self.pdf_path.set(path)
        if not self.output_dir.get():
            self.output_dir.set(str(Path(path).parent))
        self._refresh_info()

    def _select_output(self):
        path = filedialog.askdirectory(title="出力先フォルダを選択")
        if path:
            self.output_dir.set(path)

    def _open_output_dir(self):
        out = self.output_dir.get().strip()
        if not out:
            messagebox.showinfo("確認", "出力先フォルダが設定されていません。")
            return
        path = Path(out)
        if not path.exists():
            messagebox.showerror("エラー", f"フォルダが存在しません:\n{out}")
            return
        try:
            os.startfile(str(path))  # Windows
        except Exception:
            try:
                import subprocess

                subprocess.Popen(["xdg-open", str(path)])
            except Exception as e:
                messagebox.showerror("エラー", f"フォルダを開けませんでした:\n{e}")

    def _refresh_info(self):
        path = self.pdf_path.get().strip()
        if not path:
            self.page_count.set(0)
            return
        if not Path(path).exists():
            messagebox.showerror("エラー", f"ファイルが見つかりません:\n{path}")
            return
        if not PDF_AVAILABLE:
            return
        try:
            count = PDFOperations.get_page_count(path)
            self.page_count.set(count)
            self._log(f"読み込み: {Path(path).name}（{count}ページ）")
            if not self.range_text.get().strip():
                self.range_text.set(f"1-{count}" if count > 0 else "")
        except Exception as e:
            self.page_count.set(0)
            self._log(f"読み込みエラー: {e}")
            messagebox.showerror("エラー", f"PDFの読み込みに失敗しました:\n{e}")

    def _validate_common(self):
        if not PDF_AVAILABLE:
            messagebox.showerror("エラー", "PyPDF2 / pypdf が必要です。")
            return None, None
        pdf = self.pdf_path.get().strip()
        out = self.output_dir.get().strip()
        if not pdf:
            messagebox.showwarning("確認", "PDFファイルを選択してください。")
            return None, None
        if not Path(pdf).exists():
            messagebox.showerror("エラー", f"ファイルが見つかりません:\n{pdf}")
            return None, None
        if not out:
            messagebox.showwarning("確認", "出力先フォルダを指定してください。")
            return None, None
        Path(out).mkdir(parents=True, exist_ok=True)
        return pdf, out

    # ------------------------------------------------------------------
    # 分割
    # ------------------------------------------------------------------

    def _run_split(self):
        if self.is_processing:
            return
        pdf, out = self._validate_common()
        if not pdf:
            return

        mode = self.split_mode.get()
        try:
            if mode == "every":
                n = int(self.pages_per_file.get().strip())
                if n < 1:
                    raise ValueError("ページ数は1以上にしてください")
            elif mode in ("ranges", "extract"):
                text = self.range_text.get().strip()
                if not text:
                    raise ValueError("ページ範囲を入力してください")
                # 事前検証
                total = self.page_count.get() or PDFOperations.get_page_count(pdf)
                if mode == "extract":
                    parse_page_ranges(text, total)
                else:
                    for part in text.split(","):
                        if part.strip():
                            parse_page_ranges(part.strip(), total)
            else:
                raise ValueError("不明な分割モードです")
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        self._set_busy(True)
        self._log("分割処理を開始します…")

        def worker():
            try:
                if mode == "every":
                    n = int(self.pages_per_file.get().strip())
                    created = PDFOperations.split_every_n_pages(pdf, out, n)
                    self._log(f"分割完了: {len(created)}個のファイルを作成しました")
                elif mode == "ranges":
                    created = PDFOperations.split_by_ranges(
                        pdf, out, self.range_text.get().strip()
                    )
                    self._log(f"範囲分割完了: {len(created)}個のファイルを作成しました")
                else:
                    total = PDFOperations.get_page_count(pdf)
                    pages = parse_page_ranges(self.range_text.get().strip(), total)
                    stem = Path(pdf).stem
                    if len(pages) == 1:
                        name = f"{stem}_extract_p{pages[0]:03d}.pdf"
                    else:
                        name = f"{stem}_extract_p{pages[0]:03d}-{pages[-1]:03d}.pdf"
                    out_path = unique_output_path(out, name)
                    PDFOperations.extract_pages(pdf, out_path, pages)
                    created = [out_path]
                    self._log(f"抽出完了: {out_path.name}（{len(pages)}ページ）")

                for p in created[:20]:
                    self._log(f"  → {Path(p).name}")
                if len(created) > 20:
                    self._log(f"  …他 {len(created) - 20} ファイル")

                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "完了",
                        f"分割が完了しました。\n作成ファイル数: {len(created)}\n出力先: {out}",
                    ),
                )
            except Exception as e:
                logger.exception("分割エラー")
                self._log(f"分割エラー: {e}")
                self.root.after(
                    0, lambda: messagebox.showerror("エラー", f"分割に失敗しました:\n{e}")
                )
            finally:
                self._set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # 回転
    # ------------------------------------------------------------------

    def _run_rotate(self):
        if self.is_processing:
            return
        pdf, out = self._validate_common()
        if not pdf:
            return

        angle = self.rotate_angle.get()
        try:
            total = self.page_count.get() or PDFOperations.get_page_count(pdf)
            if self.rotate_target.get() == "selected":
                text = self.rotate_pages_text.get().strip()
                if not text:
                    raise ValueError("回転するページを入力してください")
                pages = parse_page_ranges(text, total)
            else:
                pages = None
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        self._set_busy(True)
        target_desc = "全ページ" if pages is None else f"{len(pages)}ページ"
        self._log(f"回転処理を開始します（{target_desc} / {angle}°）…")

        def worker():
            try:
                stem = Path(pdf).stem
                name = f"{stem}_rotated_{angle}.pdf"
                out_path = unique_output_path(out, name)
                PDFOperations.rotate_pages(pdf, out_path, angle, pages)
                self._log(f"回転完了: {out_path.name}")
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "完了",
                        f"回転が完了しました。\n出力: {out_path}",
                    ),
                )
            except Exception as e:
                logger.exception("回転エラー")
                self._log(f"回転エラー: {e}")
                self.root.after(
                    0, lambda: messagebox.showerror("エラー", f"回転に失敗しました:\n{e}")
                )
            finally:
                self._set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # JPEG変換
    # ------------------------------------------------------------------

    def _run_jpeg(self):
        if self.is_processing:
            return
        if not PDF2IMAGE_AVAILABLE:
            messagebox.showerror(
                "ライブラリ不足",
                "pdf2image がインストールされていません。\n\npip install pdf2image",
            )
            return
        if self.poppler_path is None:
            messagebox.showerror(
                "Poppler 不足",
                "JPEG変換には Poppler が必要です。\n\n"
                "Poppler for Windows をインストールし、\n"
                "環境変数 POPPLER_PATH に bin フォルダのパスを設定してください。\n"
                "例: C:\\Program Files\\poppler\\Library\\bin",
            )
            return

        pdf, out = self._validate_common()
        if not pdf:
            return

        try:
            dpi = int(self.jpeg_dpi.get().strip())
            if dpi < 72 or dpi > 600:
                raise ValueError("DPI は 72〜600 の範囲で指定してください")
            quality = int(self.jpeg_quality.get().strip())
            if quality < 1 or quality > 95:
                raise ValueError("画質は 1〜95 の範囲で指定してください")

            total = self.page_count.get() or PDFOperations.get_page_count(pdf)
            if self.jpeg_target.get() == "selected":
                text = self.jpeg_pages_text.get().strip()
                if not text:
                    raise ValueError("変換するページを入力してください")
                pages = parse_page_ranges(text, total)
            else:
                pages = None
        except Exception as e:
            messagebox.showerror("入力エラー", str(e))
            return

        self._set_busy(True)
        target_desc = "全ページ" if pages is None else f"{len(pages)}ページ"
        self._log(f"JPEG変換を開始します（{target_desc} / {dpi} DPI / 画質 {quality}）…")

        def worker():
            try:
                created = PDFOperations.convert_to_jpeg(
                    pdf,
                    out,
                    dpi=dpi,
                    quality=quality,
                    page_numbers=pages,
                    poppler_path=self.poppler_path or None,
                )
                self._log(f"JPEG変換完了: {len(created)}枚の画像を作成しました")
                for p in created[:20]:
                    self._log(f"  → {Path(p).name}")
                if len(created) > 20:
                    self._log(f"  …他 {len(created) - 20} ファイル")

                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "完了",
                        f"JPEG変換が完了しました。\n作成ファイル数: {len(created)}\n出力先: {out}",
                    ),
                )
            except Exception as e:
                logger.exception("JPEG変換エラー")
                self._log(f"JPEG変換エラー: {e}")
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "エラー", f"JPEG変換に失敗しました:\n{e}"
                    ),
                )
            finally:
                self._set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    def _on_closing(self):
        if self.is_processing:
            if not messagebox.askyesno("確認", "処理中です。終了しますか？"):
                return
        logger.info("アプリケーションを終了します")
        self.root.quit()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        # Windowsで少し見やすいテーマを試す
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    PDFEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
