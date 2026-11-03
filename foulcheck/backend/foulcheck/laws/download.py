"""Download the official Laws PDF for the configured edition."""

import shutil
import urllib.request

from foulcheck.config import laws_config


def download(force: bool = False) -> None:
    cfg = laws_config()
    if cfg.pdf_path.exists() and not force:
        print(f"Already have {cfg.pdf_path}")
        return
    cfg.pdf_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {cfg.label} from {cfg.pdf_url}")
    # the server answers 403 to urllib's default User-Agent
    request = urllib.request.Request(cfg.pdf_url, headers={"User-Agent": "foulcheck/1.0"})
    with urllib.request.urlopen(request) as response, cfg.pdf_path.open("wb") as out:
        shutil.copyfileobj(response, out)
    print(f"Saved {cfg.pdf_path} ({cfg.pdf_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    download()
