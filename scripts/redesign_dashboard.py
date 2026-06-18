"""
Dashboard Senior Redesign Script
- Standardizes card/chart styling across all pages
- Adds drill-through button on Transfer Analysis page
- Removes unused tooltip pages
"""
import json
import os
import shutil
import uuid

BASE = r"C:\Users\MONSTER\OneDrive\Belgeler\Footbball Analyze\powerbi\workspace\FootballPlayerAnalysis\Report\definition\pages"

# ── Design tokens ──────────────────────────────────────────────
GREEN_DARK   = "#285D3D"
GREEN_MED    = "#8BC99A"
GREEN_LIGHT  = "#F6FBF5"
GREEN_SHADOW = "#6FA56D"
TEXT_DARK    = "#20323F"
WHITE        = "#FFFFFF"

def literal(v):
    return {"expr": {"Literal": {"Value": v}}}

def solid_color(hex_color):
    return {"solid": {"color": literal(f"'{hex_color}'")}}

# ── Container styling helpers ───────────────────────────────────

def make_container_style(bg=GREEN_LIGHT, border=GREEN_MED, radius=10, shadow=GREEN_SHADOW, shadow_trans=60):
    return {
        "background": [{"properties": {
            "show": literal("true"),
            "color": solid_color(bg),
            "transparency": literal("0D")
        }}],
        "border": [{"properties": {
            "show": literal("true"),
            "color": solid_color(border),
            "radius": literal(f"{radius}D")
        }}],
        "dropShadow": [{"properties": {
            "show": literal("true"),
            "color": solid_color(shadow),
            "transparency": literal(f"{shadow_trans}D"),
            "angle": literal("45D"),
            "position": literal("'Outer'"),
            "size": literal("10D"),
            "blur": literal("5D")
        }}]
    }


def make_title_style(text, font_size=9, color=GREEN_DARK, bold=True, align="center"):
    return {"title": [{"properties": {
        "show": literal("true"),
        "text": literal(f"'{text}'"),
        "alignment": literal(f"'{align}'"),
        "bold": literal("true" if bold else "false"),
        "fontSize": literal(f"{font_size}D"),
        "fontColor": solid_color(color),
        "fontFamily": literal("'Segoe UI'")
    }}]}


def apply_card_improvements(vis):
    """Increase card value font + shadow + keep existing bg/border."""
    objects = vis.get("visual", {}).get("objects", {})

    # Bigger value label
    labels = objects.get("labels", [])
    if labels:
        for lbl in labels:
            props = lbl.get("properties", {})
            props["fontSize"] = literal("24D")
            # Ensure bold
            props["bold"] = literal("true")
        objects["labels"] = labels
    else:
        objects["labels"] = [{"properties": {
            "fontSize": literal("24D"),
            "bold": literal("true"),
        }}]

    # Category labels off
    objects["categoryLabels"] = [{"properties": {"show": literal("false")}}]

    vis["visual"]["objects"] = objects

    # Improve container
    vco = vis["visual"].get("visualContainerObjects", {})
    if "dropShadow" in vco:
        vco["dropShadow"][0]["properties"]["transparency"] = literal("55D")
        vco["dropShadow"][0]["properties"]["size"] = literal("12D")
    if "border" in vco:
        vco["border"][0]["properties"]["radius"] = literal("10D")
    if "title" in vco:
        # Title font size consistency
        title_props = vco["title"][0]["properties"]
        title_props["fontSize"] = literal("8D")
        title_props["fontColor"] = solid_color(TEXT_DARK)
        title_props["alignment"] = literal("'center'")
    vis["visual"]["visualContainerObjects"] = vco
    return vis


def apply_chart_improvements(vis):
    """Ensure chart has bg/border/shadow; improve title styling."""
    vco = vis["visual"].get("visualContainerObjects", {})

    # Background
    if "background" not in vco:
        vco["background"] = make_container_style()["background"]
    else:
        vco["background"][0]["properties"]["color"] = solid_color(GREEN_LIGHT)
        vco["background"][0]["properties"]["show"] = literal("true")

    # Border
    if "border" not in vco:
        vco["border"] = make_container_style()["border"]
    else:
        vco["border"][0]["properties"]["radius"] = literal("10D")
        vco["border"][0]["properties"]["color"] = solid_color(GREEN_MED)
        vco["border"][0]["properties"]["show"] = literal("true")

    # Shadow
    if "dropShadow" not in vco:
        vco["dropShadow"] = make_container_style()["dropShadow"]
    else:
        vco["dropShadow"][0]["properties"]["transparency"] = literal("60D")

    # Title
    if "title" in vco:
        tp = vco["title"][0]["properties"]
        tp["fontSize"] = literal("9D")
        tp["fontColor"] = solid_color(GREEN_DARK)
        tp["bold"] = literal("true")
        tp["alignment"] = literal("'center'")

    vis["visual"]["visualContainerObjects"] = vco
    return vis


def apply_slicer_improvements(vis):
    """Clean up slicer container."""
    vco = vis["visual"].get("visualContainerObjects", {})
    if "border" in vco:
        vco["border"][0]["properties"]["radius"] = literal("8D")
    if "title" in vco:
        vco["title"][0]["properties"]["fontSize"] = literal("8D")
        vco["title"][0]["properties"]["fontColor"] = solid_color(TEXT_DARK)
        vco["title"][0]["properties"]["bold"] = literal("true")
    vis["visual"]["visualContainerObjects"] = vco
    return vis


CHART_TYPES = {
    "clusteredBarChart", "clusteredColumnChart", "donutChart",
    "scatterChart", "lineStackedColumnComboChart", "treemap",
    "pivotTable", "tableEx", "lineChart", "areaChart", "waterfallChart",
    "funnel", "gauge", "kpi", "card100", "multiRowCard",
    "ribbonChart", "stackedBarChart", "stackedColumnChart",
    "hundredPercentStackedBarChart", "hundredPercentStackedColumnChart",
}

SLICER_TYPES = {"slicer", "advancedSlicerVisual"}

# ── Drill-through button for Transfer page ─────────────────────

TRANSFER_PAGE_ID = "292e3d92e92693c05047"
DRILLTHROUGH_PAGE_ID = "91edaa93bbbdbbc8e854"
ML_PAGE_ID = "1f4c5c8000149b2e2be8"
ML_DRILLTHROUGH_PAGE_ID = "MLPlayerDetail"

def make_drillthrough_button(name, x, y, z, width, height, tab_order, dest_page_id, label="↗ Oyuncu Detayı"):
    """Creates a styled drill-through action button visual."""
    return {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.10.0/schema.json",
        "name": name,
        "position": {
            "x": x, "y": y, "z": z,
            "height": height, "width": width,
            "tabOrder": tab_order
        },
        "visual": {
            "visualType": "actionButton",
            "objects": {
                "icon": [{"properties": {
                    "shapeType": literal("'blank'")
                }, "selector": {"id": "default"}}],
                "text": [
                    {"properties": {"show": literal("true")}},
                    {"properties": {
                        "text": literal(f"'{label}'"),
                        "fontColor": solid_color(WHITE),
                        "bold": literal("true"),
                        "fontSize": literal("9D"),
                        "horizontalAlignment": literal("'center'")
                    }, "selector": {"id": "default"}},
                    {"properties": {
                        "fontColor": solid_color("#E6FF00"),
                        "fontSize": literal("10D"),
                        "bold": literal("true")
                    }, "selector": {"id": "hover"}},
                    {"properties": {
                        "fontColor": solid_color(WHITE),
                        "fontSize": literal("9D")
                    }, "selector": {"id": "selected"}}
                ],
                "fill": [
                    {"properties": {
                        "fillColor": solid_color(GREEN_DARK),
                        "transparency": literal("0D")
                    }, "selector": {"id": "default"}},
                    {"properties": {
                        "fillColor": solid_color("#1A4A2E"),
                        "transparency": literal("0D")
                    }, "selector": {"id": "hover"}},
                    {"properties": {
                        "fillColor": solid_color(GREEN_DARK),
                        "transparency": literal("0D")
                    }, "selector": {"id": "selected"}}
                ],
                "outline": [{"properties": {
                    "show": literal("false")
                }}],
                "shape": [{"properties": {
                    "shapeType": literal("'roundedRectangle'")
                }}]
            },
            "visualContainerObjects": {
                "visualLink": [{"properties": {
                    "show": literal("true"),
                    "type": literal("'Drillthrough'"),
                    "drillthroughSection": literal(f"'{dest_page_id}'")
                }}]
            },
            "drillFilterOtherVisuals": True
        }
    }


# ── Section header textbox improvement ─────────────────────────

def improve_textbox(vis):
    """Improve section header textboxes for better visual hierarchy."""
    objects = vis.get("visual", {}).get("objects", {})
    general = objects.get("general", [])
    if not general:
        return vis
    for g in general:
        paragraphs = g.get("properties", {}).get("paragraphs", [])
        for para in paragraphs:
            for run in para.get("textRuns", []):
                style = run.get("textStyle", {})
                # Bump up slightly, ensure consistent color
                current_size = style.get("fontSize", "9pt")
                if current_size in ("8pt", "9pt", "10pt"):
                    style["fontSize"] = "9pt"
                style["color"] = GREEN_DARK
                style["bold"] = True if style.get("bold") else style.get("bold", False)
                run["textStyle"] = style
        g["properties"]["paragraphs"] = paragraphs
    objects["general"] = general
    vis["visual"]["objects"] = objects
    return vis


# ── Main processing ─────────────────────────────────────────────

def process_page(page_id):
    visuals_dir = os.path.join(BASE, page_id, "visuals")
    if not os.path.exists(visuals_dir):
        return 0

    changed = 0
    for vis_name in os.listdir(visuals_dir):
        vis_path = os.path.join(visuals_dir, vis_name, "visual.json")
        if not os.path.exists(vis_path):
            continue

        with open(vis_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        vis_type = data.get("visual", {}).get("visualType", "")

        if vis_type == "card":
            data = apply_card_improvements(data)
            changed += 1
        elif vis_type in CHART_TYPES:
            data = apply_chart_improvements(data)
            changed += 1
        elif vis_type in SLICER_TYPES:
            data = apply_slicer_improvements(data)
            changed += 1
        elif vis_type == "textbox":
            data = improve_textbox(data)
            changed += 1

        with open(vis_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    return changed


def add_drillthrough_button(page_id, dest_page_id, x, y, z, w, h, tab, label):
    visuals_dir = os.path.join(BASE, page_id, "visuals")
    btn_name = f"drillbtn_{page_id[:8]}"
    btn_dir = os.path.join(visuals_dir, btn_name)
    os.makedirs(btn_dir, exist_ok=True)
    btn_data = make_drillthrough_button(btn_name, x, y, z, w, h, tab, dest_page_id, label)
    with open(os.path.join(btn_dir, "visual.json"), "w", encoding="utf-8") as f:
        json.dump(btn_data, f, indent=2, ensure_ascii=False)
    print(f"  Added drillthrough button '{btn_name}' on page {page_id}")


def remove_tooltip_pages():
    pages_json_path = os.path.join(BASE, "pages.json")
    with open(pages_json_path, "r", encoding="utf-8") as f:
        pages_data = json.load(f)

    tooltip_pages = ["tooltip_transfer_p011", "tooltip_pred_p012"]
    original_order = pages_data["pageOrder"]
    pages_data["pageOrder"] = [p for p in original_order if p not in tooltip_pages]

    with open(pages_json_path, "w", encoding="utf-8") as f:
        json.dump(pages_data, f, indent=2, ensure_ascii=False)

    # Remove directories
    for tp in tooltip_pages:
        tp_dir = os.path.join(BASE, tp)
        if os.path.exists(tp_dir):
            def handle_err(func, path, exc):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(tp_dir, onerror=handle_err)
            print(f"  Removed tooltip page directory: {tp}")

    print(f"  pages.json: removed {len(tooltip_pages)} tooltip entries, kept {len(pages_data['pageOrder'])} pages")


def main():
    # Main pages to process (exclude drillthrough, tooltip pages)
    main_pages = [
        "5cb4db7e746975558322",   # Home
        "d2bc1e6a078c5c5b125c",   # Oyuncu Performans Analizi
        "24c53960ddc19662d824",   # Oyuncu Segmentasyonu
        "25f58efd2bb140e62be9",   # Kulüp ve Lig Analizi
        "4c63ad904b1db6e0d156",   # Transfer Başarısı Tahmini
        "292e3d92e92693c05047",   # Transfer ve Piyasa Değeri Analizi
        "1f4c5c8000149b2e2be8",   # Oyuncu Piyasa Değeri Tahmini
        "MLModelPerformance",      # ML Model Güvenilirliği
        # Drillthrough pages also benefit from improved styling:
        "91edaa93bbbdbbc8e854",   # Transfer Oyuncu Detayi
        "MLPlayerDetail",          # Oyuncu Tahmin Detayi
    ]

    print("=== Dashboard Senior Redesign ===\n")

    # 1. Remove tooltip pages
    print("1. Removing unused tooltip pages...")
    remove_tooltip_pages()

    # 2. Process all pages
    print("\n2. Applying design improvements to visuals...")
    total = 0
    for page_id in main_pages:
        count = process_page(page_id)
        total += count
        print(f"  Page {page_id[:20]}... {count} visuals updated")

    print(f"\n   Total visuals updated: {total}")

    # 3. Add drill-through buttons
    print("\n3. Adding drill-through buttons...")

    # On Transfer Analysis page — near "Kayıt Listesi" table (613,470 362x225)
    # Button placement: right side of section header row, just above the table
    add_drillthrough_button(
        page_id=TRANSFER_PAGE_ID,
        dest_page_id=DRILLTHROUGH_PAGE_ID,
        x=835, y=444,
        z=30000, w=140, h=22,
        tab=30000,
        label="↗ Oyuncu Detayı"
    )

    # On ML page — near "Tahmin Listesi" table (458,471 512x225)
    # Button placement: right side of section header
    add_drillthrough_button(
        page_id=ML_PAGE_ID,
        dest_page_id=ML_DRILLTHROUGH_PAGE_ID,
        x=860, y=444,
        z=30000, w=140, h=22,
        tab=30000,
        label="↗ Tahmin Detayı"
    )

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
