"""Generate high-resolution biblical maps with matplotlib + cartopy."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import numpy as np
from pathlib import Path
from bible_places import BIBLICAL_PLACES


def generate_chapter_map(places: list[dict], routes: list[dict], events: list[dict],
                         title: str, output_path: Path, dpi: int = 200) -> Path:
    """Generate a high-res map PNG for a chapter study.
    
    Args:
        places: [{"name": "Jerusalem", "role": "capital city"}, ...]
        routes: [{"from": "Egypt", "to": "Sinai", "label": "Exodus route"}, ...]
        events: [{"place": "Jerusalem", "event": "Temple dedication"}, ...]
        title: Map title
        output_path: Where to save the PNG
        dpi: Resolution (200 = high quality zoomable)
    """
    # Resolve coordinates
    resolved_places = []
    for p in places:
        name_lower = p["name"].lower()
        coords = BIBLICAL_PLACES.get(name_lower)
        if not coords:
            # Try partial match
            for key, val in BIBLICAL_PLACES.items():
                if name_lower in key or key in name_lower:
                    coords = val
                    break
        if coords:
            resolved_places.append({**p, "lat": coords[0], "lng": coords[1]})

    if not resolved_places:
        return None

    # Calculate map extent with padding
    lats = [p["lat"] for p in resolved_places]
    lngs = [p["lng"] for p in resolved_places]
    lat_pad = max((max(lats) - min(lats)) * 0.3, 1.5)
    lng_pad = max((max(lngs) - min(lngs)) * 0.3, 2.0)
    extent = [min(lngs) - lng_pad, max(lngs) + lng_pad,
              min(lats) - lat_pad, max(lats) + lat_pad]

    # Create figure
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_extent(extent)

    # Map features
    ax.add_feature(cfeature.LAND, facecolor='#f5e6d3', edgecolor='none')
    ax.add_feature(cfeature.OCEAN, facecolor='#c6e2ff')
    ax.add_feature(cfeature.COASTLINE, linewidth=0.5, color='#666')
    ax.add_feature(cfeature.BORDERS, linewidth=0.3, linestyle=':', color='#999')
    ax.add_feature(cfeature.RIVERS, linewidth=0.5, color='#4a90d9', alpha=0.7)
    ax.add_feature(cfeature.LAKES, facecolor='#c6e2ff', edgecolor='#4a90d9', linewidth=0.3)

    # Draw routes
    colors_route = ['#d32f2f', '#1976d2', '#388e3c', '#f57c00', '#7b1fa2']
    for i, route in enumerate(routes):
        from_lower = route.get("from", "").lower()
        to_lower = route.get("to", "").lower()
        from_coords = BIBLICAL_PLACES.get(from_lower)
        to_coords = BIBLICAL_PLACES.get(to_lower)
        if from_coords and to_coords:
            color = colors_route[i % len(colors_route)]
            ax.plot([from_coords[1], to_coords[1]], [from_coords[0], to_coords[0]],
                    color=color, linewidth=2.5, linestyle='--', alpha=0.8,
                    transform=ccrs.PlateCarree(), zorder=3)
            # Arrow at midpoint
            mid_lng = (from_coords[1] + to_coords[1]) / 2
            mid_lat = (from_coords[0] + to_coords[0]) / 2
            ax.annotate('', xy=(to_coords[1], to_coords[0]),
                       xytext=(mid_lng, mid_lat),
                       arrowprops=dict(arrowstyle='->', color=color, lw=2),
                       transform=ccrs.PlateCarree(), zorder=3)
            if route.get("label"):
                ax.text(mid_lng, mid_lat + 0.15, route["label"],
                       fontsize=7, ha='center', color=color, style='italic',
                       transform=ccrs.PlateCarree(), zorder=5)

    # Plot places
    event_places = {e.get("place", "").lower() for e in events}
    texts = []
    for p in resolved_places:
        is_event = p["name"].lower() in event_places
        marker = '*' if is_event else 'o'
        size = 150 if is_event else 80
        color = '#d32f2f' if is_event else '#1565c0'
        ax.scatter(p["lng"], p["lat"], s=size, c=color, marker=marker,
                  edgecolors='white', linewidths=0.8, zorder=10,
                  transform=ccrs.PlateCarree())
        texts.append(ax.text(p["lng"], p["lat"], p["name"],
               fontsize=8, fontweight='bold', color='#333',
               transform=ccrs.PlateCarree(), zorder=11))

    # Adjust labels to avoid overlap, with leader lines
    from adjustText import adjust_text
    adjust_text(texts, ax=ax,
                arrowprops=dict(arrowstyle='-', color='#666', lw=0.7),
                expand=(1.5, 1.5), force_text=(0.8, 0.8),
                force_points=(0.5, 0.5))

    # Event annotations
    for e in events:
        place_lower = e.get("place", "").lower()
        coords = BIBLICAL_PLACES.get(place_lower)
        if coords:
            ax.annotate(e["event"], xy=(coords[1], coords[0]),
                       xytext=(coords[1] + 0.3, coords[0] - 0.3),
                       fontsize=6.5, color='#b71c1c', style='italic',
                       arrowprops=dict(arrowstyle='->', color='#b71c1c', lw=0.8),
                       transform=ccrs.PlateCarree(), zorder=12,
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='#fff3e0', alpha=0.8))

    # Title and legend
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    legend_elements = [
        Line2D([0], [0], marker='*', color='w', markerfacecolor='#d32f2f',
               markersize=12, label='Key events'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#1565c0',
               markersize=8, label='Locations mentioned'),
        Line2D([0], [0], color='#d32f2f', linewidth=2, linestyle='--', label='Routes/journeys'),
    ]
    ax.legend(handles=legend_elements, loc='lower left', fontsize=8, framealpha=0.9)

    # Grid
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.5)
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {'size': 7}
    gl.ylabel_style = {'size': 7}

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(str(output_path), dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close()
    return output_path
