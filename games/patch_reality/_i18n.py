"""Chinese display glossary for patch_reality interactive (`play.py --lang zh`).

The engine, `get_valid_actions()`, `solve.py`, and `main.py` ALWAYS use the
canonical English tokens below as the single source of truth. This map is
consulted ONLY to (a) render Chinese token names in the zh menu / scene intro /
status, and (b) reverse-map a typed Chinese label back to its canonical action
(see ``PatchRealityGame._canonicalize_zh``). Unknown or numeric tokens
(e.g. ``+15%``, ``+0.5s``) fall back to verbatim English.

Terms are aligned with the prose already translated in ``levels_hard/*.yaml``.
This file is meant to be human-reviewed/edited — keep one canonical token per
line, grouped by category.
"""

# Canonical English token -> Simplified Chinese display name.
TOKEN_ZH = {
    # ── Verbs (action grammar) ──────────────────────────────────────────────
    "observe": "观察",
    "patch": "修补",
    "audit": "审计",
    "wait": "等待",
    "diagnose": "诊断",
    "predict": "预测",
    "anchor": "锚定",
    "check_anchor": "检视锚点",
    "reinforce_anchor": "强化锚点",
    "status": "查看状态",
    "help": "玩法说明",

    # ── Diagnosis dimensions ────────────────────────────────────────────────
    "source": "来源",
    "type": "类型",
    "strategy": "策略",

    # ── Resources ───────────────────────────────────────────────────────────
    "reality_stability": "现实稳定度",
    "memory": "记忆",
    "personal_time": "个人时间",
    "existence": "存在度",
    "agent_suspicion": "探员怀疑度",

    # ── Scene objects ───────────────────────────────────────────────────────
    "coin": "硬币",
    "pavement": "人行道",
    "drain": "雨水渠",
    "cup": "玻璃杯",
    "table": "桌子",
    "residual_patch": "残留补丁",
    "key": "钥匙",
    "lighting": "灯光",
    "door_lock": "门锁",
    "hospital_ledger": "医院账本",
    "wristband": "腕带",
    "perception": "感知",
    "stairwell": "楼梯间",
    "acoustic_log": "声学记录",
    "ledger": "账本",
    "archive_queue": "归档队列",
    "security_log": "安保日志",
    "terminal": "终端",
    "platform": "平台",
    "cameras": "摄像头",
    "crowd": "人群",
    "broadcast": "广播",
    "name_record": "姓名记录",
    "name_anchor": "姓名锚点",
    "agent_offer": "探员提议",

    # ── Patchable properties ────────────────────────────────────────────────
    "path": "路径",
    "friction": "摩擦力",
    "state": "状态",
    "angle": "角度",
    "identity": "身份",
    "record": "记录",
    "reindex": "重建索引",
    "sync": "同步",
    "timing": "时序",
    "magnet": "磁力",
    "binding": "绑定",
    "accept": "接受",

    # ── Change values (word forms; numeric like +15% pass through verbatim) ──
    "activate": "激活",
    "align": "对齐",
    "alive": "存活",
    "bind": "绑定",
    "desync": "去同步",
    "expire": "到期",
    "halt": "停止",
    "reclaim": "夺回",
    "reconcile": "对账",
    "sign": "签署",
    "soften": "柔化",
    "solidify": "固化",
    "stabilize": "稳定",

    # ── Diagnosis option values ─────────────────────────────────────────────
    "object": "物体",
    "environment": "环境",
    "physics_conflict": "物理冲突",
    "record_conflict": "记录冲突",
    "identity_record_trap": "身份记录陷阱",
    "environment_cover": "环境掩护",
    "target_repair": "目标修复",
    "audit_first": "优先审计",
    "residual_contamination": "残留污染",
    "time_order_conflict": "时序冲突",
    "rendering_lag": "渲染延迟",
    "source_record_repair": "源记录修复",
    "public_record": "公共记录",
    "public_exposure": "公开曝光",
    "system_ledger": "系统账本",
    "ledger_trap": "账本陷阱",
    "witness_memory": "目击者记忆",
    "witness_management": "目击者管理",
    "identity_anchor": "身份锚点",
    "identity_pollution": "身份污染",
    "anchor_reclaim": "锚点夺回",
    "anchor_bind": "锚点绑定",
    "agent_contract": "探员合约",
    "contract_restriction": "合约约束",
    # (archive_queue / hospital_ledger / ledger / security_log / terminal /
    #  wristband / perception / residual_patch also appear as option values and
    #  reuse their object entries above.)

    # ── Anchor names ────────────────────────────────────────────────────────
    "black_notebook": "黑色笔记本",
    "room_anchor": "房间锚点",
    "true_name": "真名",
    "home_address": "家庭住址",
    "core_identity": "核心身份",
    "sensory_baseline": "感官基准",
    "storm_memory": "风暴记忆",
}

# `status` is both a verb (→查看状态) and a patchable property (→状态). The verb
# meaning wins in TOKEN_ZH; property display resolves via PROPERTY_OVERRIDE.
PROPERTY_OVERRIDE = {"status": "状态"}


def zh_token(token, *, as_property=False):
    """Return the Chinese display name for a canonical token (verbatim fallback)."""
    if as_property and token in PROPERTY_OVERRIDE:
        return PROPERTY_OVERRIDE[token]
    return TOKEN_ZH.get(token, token)
