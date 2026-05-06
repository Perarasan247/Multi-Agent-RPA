"""Generate architecture diagram for Excellon RPA System."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(1, 1, figsize=(1600/150, 1200/150), dpi=150)
ax.set_xlim(0, 16)
ax.set_ylim(0, 12)
ax.axis('off')
fig.patch.set_facecolor('#FAFAFA')

# --- Color palette ---
C_ENTRY_BG = '#D6EAF8'
C_ENTRY_BD = '#2980B9'
C_ORCH_BG  = '#D5F5E3'
C_ORCH_BD  = '#27AE60'
C_AGENT_BG = '#FDEBD0'
C_AGENT_BD = '#E67E22'
C_UTIL_BG  = '#E8DAEF'
C_UTIL_BD  = '#8E44AD'
C_VIS_BG   = '#FADBD8'
C_VIS_BD   = '#C0392B'
C_CFG_BG   = '#D5DBDB'
C_CFG_BD   = '#566573'
C_ARROW    = '#2C3E50'

def rounded_box(x, y, w, h, label, bg, bd, fontsize=8, bold=False, sublabel=None):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                         facecolor=bg, edgecolor=bd, linewidth=1.5, zorder=2)
    ax.add_patch(box)
    weight = 'bold' if bold else 'normal'
    ty = y + h/2 if sublabel is None else y + h*0.62
    ax.text(x + w/2, ty, label, ha='center', va='center',
            fontsize=fontsize, fontweight=weight, zorder=3, wrap=True)
    if sublabel:
        ax.text(x + w/2, y + h*0.30, sublabel, ha='center', va='center',
                fontsize=5.5, color='#555', zorder=3, style='italic')

def section_label(x, y, text, color, fontsize=9):
    ax.text(x, y, text, ha='left', va='center', fontsize=fontsize,
            fontweight='bold', color=color, zorder=3)

def arrow(x1, y1, x2, y2, color=C_ARROW, style='->', lw=1.2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, connectionstyle='arc3,rad=0'),
                zorder=4)

# ============================================================
# TITLE
# ============================================================
ax.text(8, 11.6, 'Excellon RPA System — Architecture', ha='center', va='center',
        fontsize=14, fontweight='bold', color='#2C3E50')

# ============================================================
# ENTRY POINTS
# ============================================================
section_label(0.3, 10.95, 'ENTRY POINTS', C_ENTRY_BD)
ey = 10.15
rounded_box(0.5, ey, 3.8, 0.65, 'main.py', C_ENTRY_BG, C_ENTRY_BD, 8, True,
            'CLI: --run  --api  --agent')
rounded_box(5.5, ey, 3.8, 0.65, 'run_report.py', C_ENTRY_BG, C_ENTRY_BD, 8, True,
            'Auto-date scheduling wrapper')
rounded_box(10.5, ey, 4.8, 0.65, 'FastAPI Server', C_ENTRY_BG, C_ENTRY_BD, 8, True,
            '/run-pipeline  /run-agent  /health  /status')

# ============================================================
# ORCHESTRATOR
# ============================================================
section_label(0.3, 9.55, 'ORCHESTRATOR', C_ORCH_BD)
oy = 8.55
rounded_box(0.5, oy, 4.5, 0.75, 'orchestrator/graph.py', C_ORCH_BG, C_ORCH_BD, 8, True,
            'Master LangGraph pipeline\nChains 4 agents sequentially')
rounded_box(5.8, oy, 4.5, 0.75, 'orchestrator/state.py', C_ORCH_BG, C_ORCH_BD, 8, True,
            'GlobalState\n50+ keys shared across agents')
rounded_box(11.1, oy, 4.2, 0.75, 'orchestrator/router.py', C_ORCH_BG, C_ORCH_BD, 8, True,
            'Error routing\ncontinue or fail')

# ============================================================
# AGENTS
# ============================================================
section_label(0.3, 8.0, 'AGENTS  (LangGraph sub-graphs)', C_AGENT_BD)
ay = 6.15
ah = 1.55
aw = 3.5
gap = 0.35
ax_start = 0.5

agents = [
    ('Agent 1: Login',
     'Launch app\nType credentials\nHandle popups\nVerify home screen'),
    ('Agent 2: Navigation',
     'Search report\nOpenCV / Gemini disambiguation\nClick item\nVerify opened'),
    ('Agent 3: Filter',
     'Open filter panel\nSelect dealer & checkboxes\nSet dates\nGenerate report'),
    ('Agent 4: Download',
     'Click export\nHandle Save As dialog\nDecline open\nClose app'),
]

for i, (title, desc) in enumerate(agents):
    bx = ax_start + i * (aw + gap)
    rounded_box(bx, ay, aw, ah, title, C_AGENT_BG, C_AGENT_BD, 8, True, desc)

# ============================================================
# UTILITY LAYERS
# ============================================================
section_label(0.3, 5.65, 'UTILITY LAYERS', C_UTIL_BD)

# automation/
uy = 4.3
rounded_box(0.5, uy, 15.0, 1.05, 'automation/', C_UTIL_BG, C_UTIL_BD, 9, True,
            'window_manager  ·  keyboard_mouse  ·  uia_retry  ·  popup_handler\n'
            'screenshot  ·  search_handler  ·  ui_tree_reader  ·  file_explorer_handler')

# vision/
vy = 3.05
rounded_box(0.5, vy, 7.0, 0.95, 'vision/  (AI Layer)', C_VIS_BG, C_VIS_BD, 9, True,
            'highlight_detector (OpenCV)\ngemini_verifier (Gemini 2.0 Flash API)')

# config/
rounded_box(8.5, vy, 7.0, 0.95, 'config/', C_CFG_BG, C_CFG_BD, 9, True,
            'settings.py (.env loader)\nreport_loader.py (reports.json)')

# ============================================================
# ARROWS — Entry → Orchestrator
# ============================================================
for ex in [2.4, 7.4, 12.9]:
    arrow(ex, ey, ex, oy + 0.75 + 0.08)

# Orchestrator internal arrows (state ↔ graph, router ↔ graph)
arrow(5.0, oy + 0.375, 5.8, oy + 0.375, style='<->')
arrow(10.3, oy + 0.375, 11.1, oy + 0.375, style='<->')

# Orchestrator → Agents
for i in range(4):
    bx = ax_start + i * (aw + gap) + aw / 2
    arrow(bx, oy, bx, ay + ah + 0.08)

# Agent chaining arrows (1→2→3→4)
for i in range(3):
    x1 = ax_start + i * (aw + gap) + aw
    x2 = ax_start + (i + 1) * (aw + gap)
    mid_y = ay + ah / 2
    arrow(x1, mid_y, x2, mid_y, color=C_AGENT_BD, lw=1.8, style='->')

# Agents → automation (all agents)
for i in range(4):
    bx = ax_start + i * (aw + gap) + aw / 2
    arrow(bx, ay, bx, uy + 1.05 + 0.08, color=C_UTIL_BD, lw=0.8, style='->')

# Agent 2 → vision (special)
a2_cx = ax_start + 1 * (aw + gap) + aw / 2
arrow(a2_cx - 0.4, ay, 3.5, vy + 0.95 + 0.08, color=C_VIS_BD, lw=1.0, style='->')

# Config used by all (dashed-style via dotted arrows from config upward)
for tx, ty in [(12.0, uy + 1.05 + 0.08), (12.0, oy)]:
    ax.annotate('', xy=(12.0, ty), xytext=(12.0, vy + 0.95 + 0.05),
                arrowprops=dict(arrowstyle='->', color=C_CFG_BD, lw=0.8,
                                linestyle='dashed'), zorder=4)

# ============================================================
# FLOW SUMMARY (bottom)
# ============================================================
flow_y = 2.3
ax.text(8, flow_y, 'Pipeline Flow:  Entry Point  →  Orchestrator  →  Agent 1  →  Agent 2  →  Agent 3  →  Agent 4  →  Success / Fail',
        ha='center', va='center', fontsize=8, fontweight='bold', color='#2C3E50',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='#F9E79F', edgecolor='#F1C40F', linewidth=1.2))

# ============================================================
# LEGEND
# ============================================================
legend_items = [
    ('Entry Points', C_ENTRY_BG, C_ENTRY_BD),
    ('Orchestrator', C_ORCH_BG, C_ORCH_BD),
    ('Agents', C_AGENT_BG, C_AGENT_BD),
    ('Automation Utils', C_UTIL_BG, C_UTIL_BD),
    ('Vision / AI', C_VIS_BG, C_VIS_BD),
    ('Config', C_CFG_BG, C_CFG_BD),
]
lx = 1.0
ly = 1.5
for i, (lbl, bg, bd) in enumerate(legend_items):
    xi = lx + i * 2.5
    box = FancyBboxPatch((xi, ly), 0.4, 0.3, boxstyle="round,pad=0.05",
                         facecolor=bg, edgecolor=bd, linewidth=1.2, zorder=2)
    ax.add_patch(box)
    ax.text(xi + 0.55, ly + 0.15, lbl, ha='left', va='center', fontsize=6.5, color='#333', zorder=3)

plt.tight_layout(pad=0.5)
plt.savefig('d:/Projects/excellon-rpa-system/architecture_diagram.png', dpi=150,
            bbox_inches='tight', facecolor=fig.get_facecolor())
print('Diagram saved successfully.')
