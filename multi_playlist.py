import requests
import json
from datetime import datetime
from pathlib import Path
# 📂 Đặt thư mục lưu file đầu ra
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
SOURCES = [
    {"name": "Socolive", "url": "https://hxcv.site/socolive", "output": OUTPUT_DIR /"socolive.m3u"},
    {"name": "Hoadao", "url": "https://hxcv.site/hoadao", "output": OUTPUT_DIR /"hoadao.m3u"},
    {"name": "Vankhanh", "url": "https://hxcv.site/vankhanh", "output": OUTPUT_DIR /"vankhanh.m3u"},
    {"name": "Chuoichien", "url": "https://hxcv.site/chuoichien", "output": OUTPUT_DIR /"chuoichien.m3u"},
    {"name": "LuongSon", "url": "https://hxcv.site/luongson", "output": OUTPUT_DIR /"luongson.m3u"},
    # {"name": "KhanDaiA", "url": "https://hxcv.site/khandaia", "output": OUTPUT_DIR /"khandaia.m3u"}, # chưa chạy được
    # {"name": "BunCha", "url": "https://hxcv.site/buncha", "output": OUTPUT_DIR /"buncha.m3u"}, # chưa chạy được
    {"name": "GaVang", "url": "https://hxcv.site/gavang", "output": OUTPUT_DIR /"gavang.m3u"}, # chưa chạy được
]

ALL_OUTPUT = OUTPUT_DIR / "all.m3u"

def fetch_json(url):
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ Lỗi lấy JSON từ {url}: {e}")
        return None

def fetch_stream_links(remote_url):
    data = fetch_json(remote_url)
    if not data or "stream_links" not in data:
        return []
    links = []
    for s in data.get("stream_links", []):
        if not s.get("url"):
            continue
        headers = {h["key"]: h["value"] for h in s.get("request_headers", [])}
        links.append({
            "name": s.get("name", "Unnamed"),
            "url": s["url"],
            "referer": headers.get("Referer")
        })
    return links

def extract_channels(data):
    channels = []
    def walk(node):
        if isinstance(node, dict):
            if "channels" in node:
                channels.extend(node["channels"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(data)
    return channels

def process_source(name, base_url, output_file):
    print(f"\n==============================")
    print(f"🛰️  Đang xử lý nguồn {name}: {base_url}")
    print(f"==============================")

    root = fetch_json(base_url)
    if not root:
        print(f"❌ Không lấy được dữ liệu từ {base_url}")
        return []

    channels = extract_channels(root)
    if not channels:
        print(f"⚠️  Không tìm thấy channel nào trong {name}")
        return []

    all_entries = []

    for ch in channels:
        match_name = ch.get("name", "NoName")
        img = ch.get("image", {}).get("url")
        league_name = ch.get("league_name") or ch.get("category") or "Unknown League"

        # Giờ thi đấu
        time_str = ch.get("start_time") or ch.get("time") or ""
        if time_str:
            try:
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                local_time = dt.astimezone().strftime("%H:%M")
            except Exception:
                local_time = time_str
            match_label = f"{match_name} - {local_time}"
        else:
            match_label = match_name

        print(f"\n⚽ {match_label} ({league_name})")
        match_entries = []

        for source in ch.get("sources", []):
            for content in source.get("contents", []):
                for stream in content.get("streams", []):
                    blv_name = stream.get("name", "").strip() or "No BLV"
                    remote_url = stream.get("remote_data", {}).get("url")
                    if not remote_url:
                        continue

                    links = fetch_stream_links(remote_url)
                    if not links:
                        continue

                    print(f"   • {blv_name}: {len(links)} link(s)")
                    for link in links:
                        match_entries.append({
                            "source": name,
                            "league": league_name,
                            "match": match_label,
                            "name": f"{match_label} [{blv_name} - {link['name']}]",
                            "url": link["url"],
                            "referer": link["referer"],
                            "img": img
                        })

        if not match_entries:
            print("   ⚠️  Không có stream hợp lệ.")
            continue

        all_entries.extend(match_entries)

    # Viết file riêng
    if all_entries:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for e in all_entries:
                attrs = [
                    f'group-title="{e["league"]} ▸ {e["match"]}"'
                ]
                if e["img"]:
                    attrs.append(f'tvg-logo="{e["img"]}"')
                if e["referer"]:
                    attrs.append(f'referer="{e["referer"]}"')
                attr_line = " ".join(attrs)
                f.write(f'#EXTINF:-1 {attr_line},{e["name"]}\n')
                f.write(f'{e["url"]}\n')

        print(f"🎉 Đã tạo xong file: {output_file} ({len(all_entries)} links)")
    else:
        print(f"⚠️ Không có link hợp lệ cho {name}")

    return all_entries

def generate_all_playlist(all_data):
    print("\n==============================")
    print("🧩 Gộp tất cả nguồn thành all.m3u (chia theo nguồn & trận)")
    print("==============================")

    with open(ALL_OUTPUT, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for e in all_data:
            # Gộp 3 cấp: Source ▸ League ▸ Match
            group = f'{e["source"]} ▸ {e["league"]} ▸ {e["match"]}'
            attrs = [f'group-title="{group}"']
            if e["img"]:
                attrs.append(f'tvg-logo="{e["img"]}"')
            if e["referer"]:
                attrs.append(f'referer="{e["referer"]}"')
            attr_line = " ".join(attrs)
            f.write(f'#EXTINF:-1 {attr_line},{e["name"]}\n')
            f.write(f'{e["url"]}\n')

    print(f"🎉 Đã tạo xong file tổng: {ALL_OUTPUT} ({len(all_data)} links)")

def main():
    all_entries = []
    Path("./").mkdir(exist_ok=True)

    for src in SOURCES:
        entries = process_source(src["name"], src["url"], src["output"])
        all_entries.extend(entries)

    if all_entries:
        generate_all_playlist(all_entries)
    else:
        print("❌ Không có dữ liệu hợp lệ nào để gộp.")

    if not any(OUTPUT_DIR.glob("*.m3u")):
        print("⚠️ Không có file nào được tạo trong output/. Kiểm tra nguồn dữ liệu!")
    
    # 🧮 Ghi thống kê để workflow dùng trong commit message
    stats_file = OUTPUT_DIR / "stats.txt"
    with open(stats_file, "w", encoding="utf-8") as f:
        f.write(str(len(all_entries)))

if __name__ == "__main__":
    main()
    

