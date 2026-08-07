#pyright: reportUndefinedVariable=false
# ======================================
# Game: Pyxel Multi-Stage
# Base: v0.59b (2026-02-18_22:00)
# - TILEを8→16に統一(OLD_TILE=8は参照用に残置)
# - プレイヤー/敵/アイテム/ブロックのサイズを16px化
# - 動く床などのピクセル座標を16グリッドにスナップ
# - ストンプ許容縁をTILEスケールに合わせて調整
# - 物理値(重力/ジャンプ/床Y等)は変更なし(ノータッチ)
# - エネミー追加：シューター
# - 弾関連の調整（プレイヤー、エネミー共）
# - Xダッシュ追加
# - 弾の衝突処理、ハイパーショット 対 通常ショット
# - ステージ7,8,9追加、調整
# - コード統合
# - ボスシーンショット打ち消し関連修正
# - 1ボス個性、中ボス個性構造整備
# - ボスショットバグfix,2ボス個性
# - ボス部屋bugfix
# - 背景関係修正
# - ボス設定調整
# - ３面ボス個性付け
# - ３面ボス描画
# - ４面ボス個性付け
# - ブロック等エディタ基準統一
# - ステージ４、ミサイルバグ修正
# - 中ボス基本個性付、デバッグ中ボス追加
# - 全中ボス個性、背景色変更
# - 壊せるブロック仕様変更
# - ステージ９追加、読み込みファイル拡張、デバッグ機能拡張
# - ステージ5,6,7,8,9個性付、ボス部屋リスタート時のクリア措置
# - ステージ５
# - ステージ９描画調整
# - ボス、中ボス描画指定、ステージ９バグFIX
# - コンベア、移動床fix
# - ステージ７
# - ステージ８、エネミー４種追加
# - サウンド追加
# - ミュージック追加
# - ボス等撃破演出
# - ボスサウンド、行動修正など
# - 環境変化システム導入
# - ゲームパッド対応設定
# - バグfix
# - ステージ９ギミック
# ======================================

# === ANCHOR: IMPORTS (DO NOT EDIT) ===
import pyxel
from random import randint
import random
import math
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass
from music.manager import MusicManager
# === ANCHOR END ===

# ===== DEBUG SWITCH =====
DEV_MENU = False   # 起動時は通常モード（タイトル画面の隠しコマンドで切替）

# ===== Pyxel editor resource files =====
# 通常ステージ用: これまでどおりの既存ファイル
RESOURCE_MAIN = "sekka.pyxres"
# 追加素材用: sekka.pyxres と同じフォルダに置く新規ファイル
# ※Pyxelの仕様上、load時はリソース一式が切り替わるため、
#   sekka2.pyxres 側にもプレイヤー等の共通素材をコピーしておくと安全。
RESOURCE_EXTRA = "sekka2.pyxres"
# ラスボス描画用: Stage9 final boss sprite sheet
RESOURCE_FINAL = "sekka3.pyxres"
# ステージ9のタイルマップは追加ファイル側を使う
EXTRA_TILEMAP_STAGES = {9}
# ボス部屋で追加ファイル側を使うのはステージ9のみ。
# ステージ5〜8の後半ボス/中ボスは sekka.pyxres の Image2 を使う。
EXTRA_BOSS_IMAGE_STAGES = {9}


def tilemap_stage_index(stage):
    """Return vertical stage slot inside the currently loaded .pyxres tilemaps.

    Stages 1-8 keep the old stacked layout in sekka.pyxres:
      stage 1 -> slot 0, stage 2 -> slot 1, ... stage 8 -> slot 7

    Stage 9 uses sekka2.pyxres as a separate resource file, so it starts
    from the top of TM0/TM1/TM2 in that file:
      stage 9 -> slot 0
    """
    try:
        st = int(stage)
    except Exception:
        st = 1
    if st in EXTRA_TILEMAP_STAGES:
        return 0
    return max(0, st - 1)

def tilemap_v8_row(stage):
    """8px-cell Y offset for the stage area in the loaded resource."""
    return tilemap_stage_index(stage) * 32

def tilemap_v_px_row(stage):
    """Pixel Y offset for pyxel.bltm() in the loaded resource."""
    return tilemap_stage_index(stage) * 256

# ===== Stage9 large-field helpers =====
# Stage9 は sekka2.pyxres の最上段から「通常ステージ8個分」を縦に読む。
# 横幅(WORLD_W)は従来どおり。縦だけ 256px * 8 = 2048px にする。
STAGE9_VERTICAL_SCREENS = 8

# Stage9のフィールド内ボス/中ボスは、コードで座標指定しない。
# TM2に置いた BOSS1_MARK〜BOSS8_MARK / MID1_MARK〜MID8_MARK を出現位置として読む。
# 行動範囲は同じ行の MARK_L/MARK_R、同じ列の MARK_A/MARK_U で指定する。
STAGE9_FIELD_BOSS_SPAWNS = []  # 互換用。新規配置では使わない。

def stage_vertical_screens(stage):
    return STAGE9_VERTICAL_SCREENS if int(stage) == 9 else 1

def stage_world_h(stage):
    return SCREEN_H * stage_vertical_screens(stage)

def stage_tiles_y(stage):
    return stage_world_h(stage) // TILE

def stage_tilemap_h8(stage):
    return stage_world_h(stage) // 8

# ===== Stage9 TM2 marker field boss/midboss helpers =====
STAGE9_FIELD_BOSS_MARKERS = {
    "BOSS1_MARK": 1, "BOSS2_MARK": 2, "BOSS3_MARK": 3, "BOSS4_MARK": 4,
    "BOSS5_MARK": 5, "BOSS6_MARK": 6, "BOSS7_MARK": 7, "BOSS8_MARK": 8,
}
STAGE9_FIELD_MIDBOSS_MARKERS = {
    "MID1_MARK": 1, "MID2_MARK": 2, "MID3_MARK": 3, "MID4_MARK": 4,
    "MID5_MARK": 5, "MID6_MARK": 6, "MID7_MARK": 7, "MID8_MARK": 8,
}

# ===== Stage9 gem route gimmick =====
STAGE9_GEM_REQUIRED = 15

# DEV_MENUで「MIDBOSS: 9」を選んだ場合だけ使う開始地点。
# Pyxel tilemap座標は8pxセルなので、sekka2.pyxres の tilemap(0, 248) を
# ワールド座標へ変換し、プレイヤーをその床の直上から開始させる。
DEV_STAGE9_MID_START_TM_X8 = 0
DEV_STAGE9_MID_START_TM_Y8 = 248

STAGE9_GEM_REWARDS = {
    # src_stage: (midboss gems, boss gems)
    1: (1, 4), 2: (1, 4), 3: (1, 4),
    4: (2, 5), 5: (2, 5), 6: (2, 5),
    7: (3, 6), 8: (3, 6),
}

def stage9_gem_reward_for_actor(actor):
    """Return gem count for a Stage9 historical boss/midboss actor."""
    try:
        src_stage = int(getattr(actor, "field_boss_origin_stage", getattr(actor, "field_boss_stage", 0)))
    except Exception:
        src_stage = 0
    mid_count, boss_count = STAGE9_GEM_REWARDS.get(src_stage, (0, 0))
    return int(mid_count if bool(getattr(actor, "is_midboss", False)) else boss_count)

def _stage9_scan_lr_markers(TILES_X, tx, ty, default_left_px, default_right_px):
    """MARK_L / MARK_R を探し、見つかればその間を行動範囲にする。

    ボス/中ボス用マーカーは16px単位で置くため、見た目では同じ高さでも
    1タイル上下にずれていることがある。そこで同じ行を優先しつつ、
    上下1タイルまで許容して探す。
    """
    stage_index = tilemap_stage_index(9)

    row_candidates = [ty]
    if ty - 1 >= 0:
        row_candidates.append(ty - 1)
    row_candidates.append(ty + 1)

    left_tx = None
    for row in row_candidates:
        if row < 0:
            continue
        for sx in range(tx - 1, -1, -1):
            if _kind_at_tm2(stage_index, sx, row) == "MARK_L":
                left_tx = sx
                break
        if left_tx is not None:
            break

    right_tx = None
    for row in row_candidates:
        if row < 0:
            continue
        for sx in range(tx + 1, TILES_X):
            if _kind_at_tm2(stage_index, sx, row) == "MARK_R":
                right_tx = sx
                break
        if right_tx is not None:
            break

    left_px = int(left_tx * TILE) if left_tx is not None else int(default_left_px)
    # 右端マーカーは「そのタイルの右端」まで使えるように +1 タイルする。
    right_px = int((right_tx + 1) * TILE) if right_tx is not None else int(default_right_px)

    if right_px <= left_px:
        left_px, right_px = int(default_left_px), int(default_right_px)
    return left_px, right_px

def _stage9_scan_ud_markers(TILES_Y, tx, ty, default_top_px, default_bottom_px):
    """MARK_A / MARK_U を探し、見つかれば上下行動範囲にする。

    同じ列を優先しつつ、左右1タイルまで許容して探す。
    """
    stage_index = tilemap_stage_index(9)

    col_candidates = [tx]
    if tx - 1 >= 0:
        col_candidates.append(tx - 1)
    col_candidates.append(tx + 1)

    top_ty = None
    for col in col_candidates:
        if col < 0:
            continue
        for sy in range(ty - 1, -1, -1):
            if _kind_at_tm2(stage_index, col, sy) == "MARK_A":
                top_ty = sy
                break
        if top_ty is not None:
            break

    bottom_ty = None
    for col in col_candidates:
        if col < 0:
            continue
        for sy in range(ty + 1, TILES_Y):
            if _kind_at_tm2(stage_index, col, sy) == "MARK_U":
                bottom_ty = sy
                break
        if bottom_ty is not None:
            break

    top_px = int(top_ty * TILE) if top_ty is not None else int(default_top_px)
    bottom_px = int((bottom_ty + 1) * TILE) if bottom_ty is not None else int(default_bottom_px)

    if bottom_px <= top_px:
        top_px, bottom_px = int(default_top_px), int(default_bottom_px)
    return top_px, bottom_px

def _stage9_apply_field_actor_common(actor, src_stage, tx, ty, TILES_X, TILES_Y):
    """ステージ9フィールド配置版の共通設定。

    基本は BOSSx_MARK / MIDx_MARK を「足元中央」として扱う。
    ただし Stage5/6ボスだけは、エディタ上で置いたYをそのまま描画上端として使う。
    実際の actor.x / actor.y は生成時点で補正済み。
    """
    actor.field_boss_stage = int(src_stage)
    actor.field_boss_origin_stage = int(src_stage)
    actor.stage9_invert_palette = True

    actor.field_boss_marker_tx = int(tx)
    actor.field_boss_marker_ty = int(ty)
    marker_ground_y = int((ty + 1) * TILE)

    # Stage9の縦長フィールドでは、配置時のボス中心が属する256px区画を固定保持する。
    # Stage4ボスの召喚フライヤー等が、ボスの一時的なY移動やカメラ位置によって
    # 上下の別ステージ区画へはみ出すのを防ぐために使う。
    actor_center_y = float(actor.y) + float(getattr(actor, "h", 32)) * 0.5
    actor.stage9_section = int(max(0.0, actor_center_y) // float(SCREEN_H))

    # MARK_L/R, MARK_A/U が無い時の保険範囲。
    default_left = max(0, int(actor.x) - 160)
    default_right = min(WORLD_W, int(actor.x) + int(getattr(actor, "w", 64)) + 224)
    default_top = max(0, int(actor.y) - 128)
    default_bottom = min(stage_world_h(9), int(actor.y) + int(getattr(actor, "h", 64)) + 128)

    left, right = _stage9_scan_lr_markers(TILES_X, tx, ty, default_left, default_right)
    top, bottom = _stage9_scan_ud_markers(TILES_Y, tx, ty, default_top, default_bottom)

    actor.field_boss_left = left
    actor.field_boss_right = right
    actor.field_boss_top = top
    actor.field_boss_bottom = bottom

    # 初期位置が範囲外に出ていた場合だけ安全に範囲内へ戻す。
    actor.x = clamp(float(actor.x), int(left), int(right) - int(getattr(actor, "w", 32)))
    actor.y = clamp(float(actor.y), int(top), int(bottom) - int(getattr(actor, "h", 32)))

    # Stage9では通常ボス部屋の固定 FLOOR_Y を使わず、個体ごとの接地Yを持たせる。
    # Stage3ボスは上空巡回後、MARK_U（無ければ既定の下端）まで急降下する。
    # Stage5/6ボスはマーカーYを描画上端として配置するため、実座標の下端を接地Yにする。
    if (not bool(getattr(actor, "is_midboss", False))) and int(src_stage) == 3:
        actor.field_boss_ground_y = int(bottom)
    elif (not bool(getattr(actor, "is_midboss", False))) and int(src_stage) in (5, 6):
        actor.field_boss_ground_y = int(round(float(actor.y))) + int(getattr(actor, "h", 64))
    else:
        actor.field_boss_ground_y = marker_ground_y

    # Stage1ボスの停止→扇状ショット用。
    actor.field_boss_shot_cd = 60
    actor.field_boss_stop_timer = 0
    actor.field_boss_prev_vx = getattr(actor, "vx", 0)
    # Stage9フィールド配置版では、通常ボス部屋用の game.boss_stop_timer を
    # 個体ごとに退避して使う。Stage8ボスのジャンプ後停止/Waitが共有タイマーを
    # 使って固まるのを防ぐ。
    actor.field_boss_ai_stop_timer = 0
    return actor

def parse_stage9_field_boss_markers(game):
    """TM2の BOSS1_MARK〜BOSS8_MARK から、ステージ9用フィールドボスを生成する。"""
    bosses = []
    ais = []
    if int(getattr(game, "stage", 1)) != 9:
        return bosses, ais

    stage_index = tilemap_stage_index(9)
    for ty in range(game.TILES_Y):
        for tx in range(game.TILES_X):
            kind = _kind_at_tm2(stage_index, tx, ty)
            if kind not in STAGE9_FIELD_BOSS_MARKERS:
                continue

            src_stage = STAGE9_FIELD_BOSS_MARKERS[kind]
            bd = (STAGE_BOSS_DEF.get(src_stage, {}) or {}).get("boss", DEFAULT_BOSS_DEF)

            # TM2のBOSSx_MARKは基本的に「足元中央」として扱う。
            # Stage5/6だけは、エディタで置いたYと実際の描画Yが64px近くずれていたため、
            # マーカー上端をボスの描画上端として扱う（Xは従来どおり中央合わせ）。
            boss_w = int(bd.get("w", 64))
            boss_h = int(bd.get("h", 64))
            x = tx * TILE + TILE // 2 - boss_w // 2
            if int(src_stage) in (5, 6):
                y = ty * TILE
            else:
                y = (ty + 1) * TILE - boss_h
            boss = Boss(x, y, hp=int(bd.get("hp", 30)),
                        sprite_key=bd.get("sprite_key", "BOSS1"),
                        is_midboss=False)
            boss.w = boss_w
            boss.h = boss_h
            boss.max_hp = int(bd.get("hp", 30))
            _stage9_apply_field_actor_common(boss, src_stage, tx, ty, game.TILES_X, game.TILES_Y)
            boss.score_key = (9, "field_boss", int(src_stage), int(tx), int(ty))

            ai = BossAIAdapter(game, boss)
            preset = bd.get("preset")
            if preset:
                ai.load_preset(preset)

            bosses.append(boss)
            ais.append(ai)

    return bosses, ais

def parse_stage9_field_midboss_markers(game):
    """TM2の MID1_MARK〜MID8_MARK から、ステージ9用フィールド中ボスを生成する。"""
    mids = []
    ais = []
    if int(getattr(game, "stage", 1)) != 9:
        return mids, ais

    stage_index = tilemap_stage_index(9)
    for ty in range(game.TILES_Y):
        for tx in range(game.TILES_X):
            kind = _kind_at_tm2(stage_index, tx, ty)
            if kind not in STAGE9_FIELD_MIDBOSS_MARKERS:
                continue

            src_stage = STAGE9_FIELD_MIDBOSS_MARKERS[kind]
            md = (STAGE_BOSS_DEF.get(src_stage, {}) or {}).get("mid", DEFAULT_MIDBOSS_DEF)

            # TM2のMIDx_MARKも「足元中央」として扱う。
            # マーカーの下中央を中ボスの足元中央に合わせる。
            mid_w = int(md.get("w", 32))
            mid_h = int(md.get("h", 32))
            x = tx * TILE + TILE // 2 - mid_w // 2
            y = (ty + 1) * TILE - mid_h
            mid = Boss(x, y, hp=int(md.get("hp", 10)),
                       sprite_key=md.get("sprite_key", "MID1"),
                       is_midboss=True)
            mid.w = mid_w
            mid.h = mid_h
            mid.max_hp = int(md.get("hp", 10))
            _stage9_apply_field_actor_common(mid, src_stage, tx, ty, game.TILES_X, game.TILES_Y)
            mid.score_key = (9, "field_midboss", int(src_stage), int(tx), int(ty))

            # Stage9に配置したStage4中ボスは、配置直後から更新すると
            # プレイヤー到達前に下降・自爆してしまう。
            # 同じ256px区画にプレイヤーが入り、かつ画面内に映った瞬間に
            # 初めて出現・行動開始する。以後は通常どおり更新する。
            if int(src_stage) == 4:
                mid.stage9_wait_for_visible_activation = True
                mid.stage9_visible_activated = False
                mid.stage9_section = int((float(y) + float(mid_h) * 0.5) // float(SCREEN_H))

            ai = BossAIAdapter(game, mid)
            preset = md.get("preset")
            if preset:
                ai.load_preset(preset)

            mids.append(mid)
            ais.append(ai)

    return mids, ais


def parse_stage9_dedicated_midboss_marker(game):
    """TM2の MID9_MARK からStage9専用中ボスを1体だけ生成する。

    マーカー未配置なら生成しない。座標は後からエディタだけで変更できる。
    MARK_L/R と MARK_A/U があれば行動範囲にも使用する。
    """
    if int(getattr(game, "stage", 1)) != 9:
        return None, None
    stage_index = tilemap_stage_index(9)
    for ty in range(game.TILES_Y):
        for tx in range(game.TILES_X):
            if _kind_at_tm2(stage_index, tx, ty) != "MID9_MARK":
                continue
            md = (STAGE_BOSS_DEF.get(9, {}) or {}).get("mid", DEFAULT_MIDBOSS_DEF)
            w, h = int(md.get("w", 32)), int(md.get("h", 32))
            x = tx * TILE + TILE // 2 - w // 2
            y = (ty + 1) * TILE - h
            mid = Boss(x, y, hp=int(md.get("hp", 10)),
                       sprite_key=md.get("sprite_key", "MID9"), is_midboss=True)
            mid.w, mid.h = w, h
            mid.max_hp = int(md.get("hp", 10))
            _stage9_apply_field_actor_common(mid, 9, tx, ty, game.TILES_X, game.TILES_Y)
            # 専用中ボスは歴代ボスの反転描画対象外。
            mid.stage9_invert_palette = False
            mid.score_key = (9, "dedicated_midboss", int(tx), int(ty))
            ai = BossAIAdapter(game, mid)
            preset = md.get("preset")
            if preset:
                ai.load_preset(preset)
            return mid, ai
    return None, None


# ===== 基本設定 =====
# === ANCHOR: TILE_DEFINITIONS (FIX) ===
# === Boss draw rules ===
# ボスごとの「描画状態 → フレーム番号」の対応表
#
# ・draw 側はこの表だけを見る
# ・行動ロジック / FSM / 速度計算とは分離する
# ・将来ステージをまたいで休止しても、
#   「ここを見ればどう作るか分かる」状態にする
#
# frame番号は SPRITE_UV["BOSSx"] の index
#
# 例:
#   "stop": [0]            # 固定1枚
#   "walk": [1, 2]         # 交互
#   "jump": [3]            # 固定1枚
#
BOSS_DRAW_RULES = {
    # Stage1 boss: patrol 2 / stop 1
    "BOSS1": {"stop": [0], "walk": [0, 1], "charge": [0, 1], "jump": [0]},

    # Stage2 boss: existing image layout
    "BOSS2": {"stop": [0], "walk": [1, 2], "jump": [3], "charge": [1, 2]},

    # --- Stage3 boss draw rules ---
    # 空中での通常横移動(2枚) / 突進(1枚) / 停止(1枚)
    # ※停止後の上昇は要件通り walk(2枚) を当てる
    "BOSS3": {"stop": [3], "walk": [0, 1], "charge": [2], "jump": [0, 1]},

    # --- Stage4 boss draw rules ---
    # 通常: IMAGE1 (0,192) <-> (128,192) 64x64
    # 上昇: IMAGE1 (64,192) <-> (128,192) 64x64
    "BOSS4": {"walk": [0, 2], "rise": [1, 2], "stop": [0, 2], "jump": [1, 2]},

    # Stage5 boss: patrol/rush 2 / stop 1 / jump 1
    "BOSS5": {"walk": [0, 1], "charge": [0, 1], "stop": [2], "jump": [3]},
    # Stage6 boss: patrol 2 / stop 1 / jump 1
    "BOSS6": {"walk": [0, 1], "charge": [0, 1], "stop": [2], "jump": [3]},
    # Stage7 boss: normal stop 1 / jump 1
    "BOSS7": {"stop": [0], "walk": [0], "charge": [0], "jump": [1]},
    # Stage8 boss: stop 2 / jump 1 / rush 2
    # stop alternates: Image2 (0,192) <-> Image2 (192,128)
    "BOSS8": {"stop": [0, 4], "walk": [0], "jump": [1], "charge": [2, 3]},

    # Stage9 final boss: patrol/rush/air patrol/rise 2 / stop 1 / jump/drop 1
    "FINAL": {"walk": [0, 1], "charge": [0, 1], "rise": [0, 1], "stop": [2], "jump": [3]},

    # Midboss draw rules
    "MID1": {"walk": [0, 1], "stop": [0], "jump": [0]},
    "MID2": {"walk": [0, 1], "stop": [0], "jump": [2]},
    "MID3": {"stop": [0], "walk": [0], "jump": [0]},
    "MID4": {"walk": [0, 1], "rise": [0, 1], "stop": [0, 1], "jump": [0, 1]},
    "MID5": {"walk": [0, 1], "stop": [0], "jump": [0]},
    "MID6": {"walk": [0, 1], "stop": [0], "jump": [0]},
    "MID7": {"walk": [0, 1], "stop": [0], "jump": [0]},
    "MID8": {"walk": [0, 1], "charge": [0, 1], "stop": [2], "jump": [3]},
    "MID9": {"walk": [0, 1], "charge": [0, 1], "stop": [2], "jump": [3]},
}
# === Boss draw rules END ===

TILE = 16  # 16px

def _snap8(u, v):
    # 8pxグリッドに丸める（誤記があっても一致させる保険）
    return (u // 8) * 8, (v // 8) * 8

TILES = {
    "AIR":        _snap8(0, 0),
    "FLOOR":      _snap8(32, 0), # 乗れるブロック
    "ITEM":       _snap8(48, 0),
    "BREAKABLE":  _snap8(64, 0), # 壊せるブロック
    "MOVE_H":     _snap8(80, 0),
    "MOVE_V":     _snap8(96, 0),
    "CRASH":      _snap8(112, 0), # 壊せるブロック
    "AUTO":       _snap8(128, 0),
    "GROUND":     _snap8(144, 0), # 床
    "COIN":       _snap8(160, 0), # コイン
    "MIDFLAG":    _snap8(240, 0), # 中間フラッグ
    "ONEUP":      _snap8(176, 0),
    "SCOREUP":    _snap8(192, 0),
    "POWERUP":    _snap8(208, 0),
    "HPUP":       _snap8(224, 0),
    "MIDFLAG2":   _snap8(240, 0),
    "KILL":       _snap8(144, 16),
    "SPRING":     _snap8(144, 32), 
    "SPRING2":    _snap8(160, 32), 
    "BOSS_DOOR":  _snap8(48, 16),  # 32×32（4×4 タイル）ボス扉
    "MARK_CONVEYOR": _snap8(32, 16),  # コンベア方向/速度・動く床コンベア化マーカー
    "MARK_L":     _snap8(16, 32),
    "MARK_R":     _snap8(32, 32),
    "MARK_A":     _snap8(16, 48),
    "MARK_U":     _snap8(32, 48),
    "MARK_P":     _snap8(48, 48),
    # --- TM2 enemy markers (editor placement) ---
    "E_WALKER":         _snap8(64, 48),
    "E_HOPPER":         _snap8(80, 48),
    "E_FLYER":          _snap8(96, 48),
    "E_SHOOTER":        _snap8(112, 48),
    "E_STOMP_WALKER":   _snap8(128, 48),
    "E_IMMUNE_WALKER":  _snap8(144, 48),

    # --- TM2 new enemy markers ---
    "E_WARP":           _snap8(112, 96),  # ワープ敵
    "E_CHASER_WALKER":  _snap8(96, 96),   # プレイヤー追尾ウォーカー
    "E_SPLIT_FLYER":    _snap8(128, 96),  # 増殖不死フライヤー
    "E_AIM_SHOOTER":    _snap8(144, 96),  # ハイスピードシューター

    # --- TM2 missile markers (fixed direction) ---
    # ※他の敵マーカーと座標が絶対に被らないこと
    "E_MISSILE_L":      _snap8(160, 48),  # 右→左
    "E_MISSILE_R":      _snap8(176, 48),  # 左→右
    "E_MISSILE_U":      _snap8(192, 48),  # 下→上
    "E_MISSILE_D":      _snap8(208, 48),  # 上→下

    # --- TM2 Stage9 field boss/midboss markers ---
    # ここは仮座標。あとでPyxel Editor上の未使用マーカー座標に合わせて変更OK。
    # BOSSx_MARK: ステージ9通常フィールドに歴代ボスを出す位置。
    # MIDx_MARK : ステージ9通常フィールドに歴代中ボスを出す位置。
    "BOSS1_MARK":      _snap8(96, 64),
    "BOSS2_MARK":      _snap8(112, 64),
    "BOSS3_MARK":      _snap8(128, 64),
    "BOSS4_MARK":      _snap8(144, 64),
    "BOSS5_MARK":      _snap8(160, 64),
    "BOSS6_MARK":      _snap8(176, 64),
    "BOSS7_MARK":      _snap8(192, 64),
    "BOSS8_MARK":      _snap8(208, 64),

    "MID1_MARK":       _snap8(96, 80),
    "MID2_MARK":       _snap8(112, 80),
    "MID3_MARK":       _snap8(128, 80),
    "MID4_MARK":       _snap8(144, 80),
    "MID5_MARK":       _snap8(160, 80),
    "MID6_MARK":       _snap8(176, 80),
    "MID7_MARK":       _snap8(192, 80),
    "MID8_MARK":       _snap8(208, 80),
    "MID9_MARK":       _snap8(224, 48),  # Stage9専用中ボス（エディタ配置）
    }

# ミサイルはステージ開始時には動かさず、
# プレイヤーがこの範囲に入ったら初めて発射する。
MISSILE_ACTIVATE_X_RANGE = 192
MISSILE_ACTIVATE_Y_RANGE = 128

# エディタ配置フライヤーも、ステージ開始時には動かさず、
# プレイヤーがこの範囲に入ったら初めて行動開始する。
FLYER_ACTIVATE_X_RANGE = 192
FLYER_ACTIVATE_Y_RANGE = 128

SOLID_KINDS = {
    "FLOOR", "BREAKABLE", "MOVE_H", "MOVE_V", "CRASH",
    "AUTO", "GROUND", "BOSS_DOOR", "COIN",
    "KILL", "SPRING"
}
# === ANCHOR END ===

def put_16(tm, tx, ty, u, v):
    tm.pset(tx*2+0, ty*2+0, (u//8, v//8))
    tm.pset(tx*2+1, ty*2+0, ((u+8)//8, v//8))
    tm.pset(tx*2+0, ty*2+1, (u//8, (v+8)//8))
    tm.pset(tx*2+1, ty*2+1, ((u+8)//8, (v+8)//8))

# === ANCHOR: PUT_KIND_HELPERS ===
def _get_tilemap_safe(indices):
    """
    indicesで渡されたタイルマップ番号を上から順に探して最初に使えるものを返す。
    例: _get_tilemap_safe([1,0]) → TM1が無ければTM0。
    """
    for idx in indices:
        try:
            tm = pyxel.tilemap(idx)
            try:
                tm.imgsrc = 0
            except AttributeError:
                tm.refimg = 0
            return tm
        except Exception:
            continue
    return None
# === ANCHOR END ===

def put_kind(tx, ty, kind):
    """
    16pxタイル座標 (tx, ty) に editor上の 'kind' を書き込む。
    ステージは縦積みなので、現在ステージの縦オフセット(16pxタイル単位)を足してから書く。
    """
    stage_index = tilemap_stage_index(Game._instance.stage if Game._instance else 1)
    STAGE_H_TILES16 = 16
    ty_with_offset = ty + stage_index * STAGE_H_TILES16

    # 可変レイヤは「TM1」を正（無ければTM0）
    tm_var = _get_tilemap_safe([1, 0])
    if tm_var is None:
        return  # どれも無ければ安全に無視

    u, v = TILES[kind]
    put_16(tm_var, tx, ty_with_offset, u, v)

# === ANCHOR: TILE_COLLISION_FUNC (FIX) ===

UV_TO_KIND = { _snap8(*TILES[k]): k for k in TILES }

# === ANCHOR END ===

# === Helper shims to prevent NameError (safe, minimal) ===
try:
    SCREEN_W
except NameError:
    SCREEN_W = 256
try:
    SCREEN_H
except NameError:
    SCREEN_H = 256

try:
    shoot_cb
except NameError:
    def shoot_cb(*args, **kwargs):
        # No-op callback used by older stages; safe default
        return None

try:
    spread_positions
except NameError:
    pass

# === Canonical spread helpers (unified) ===
def spread_positions(x0=0, y0=0, count=0, x_margin=16, y_top=0, y_slop=0, *, as_dict=False, spd=1):
    """Return evenly spaced positions or shooter dicts.
    If as_dict=True, returns [{'x':x,'y':y,'spd':spd}, ...] for shooters.
    """
    if not count or count <= 0:
        return []
    xs = [x0 + i * max(1, x_margin) for i in range(count)]
    ys = [max(y_top, y0) for _ in range(count)]
    coords = list(zip(xs, ys))
    if as_dict:
        return [{'x': x, 'y': y, 'spd': spd} for (x, y) in coords]
    return coords

def spread_shooters(x0=0, y0=0, count=0, spd=1, x_margin=32):
    """Backward-compatible thin wrapper using spread_positions(as_dict=True)."""
    return spread_positions(x0=x0, y0=y0, count=count, x_margin=x_margin, as_dict=True, spd=spd)

try:
    spread_shooters
except NameError:
    pass

# === Utility: global helpers ===
def snap16(v):
    return (v // TILE) * TILE

OLD_TILE = 8     # 参照用に残置(使わなくてもOK)
WORLD_SCREENS = 8
WORLD_W = SCREEN_W * WORLD_SCREENS
WORLD_H = SCREEN_H
# === ANCHOR: CONFIG_END ===

# === ANCHOR: INPUT_BINDINGS (OK TO EDIT) ===
# ポーズ用キー
PAUSE_KEY = pyxel.KEY_P
STEP_KEY  = pyxel.KEY_S

# ===== SOUND EFFECTS (OK TO EDIT) =====
# コード側で SOUND 31〜63 をゲーム効果音として本設定する。
# .pyxres側が未設定でも必ず鳴る、エディタ非依存版。
SFX = {
    "BOSS_RUSH": 31,
    "BOSS_HIT": 32,
    "SPRING_BIG": 33,
    "SPRING_BOUNCE": 34,
    "BLOCK_DULL": 35,
    "JUMP": 40,
    "SHOT": 41,
    "CHARGE_SHOT": 42,
    "ARMOR_BREAK": 43,
    "PLAYER_DAMAGE": 44,
    "STOMP": 45,
    "BLOCK_BREAK": 46,
    "BLOCK_BUMP": 47,
    "ITEM_APPEAR": 48,
    "COIN": 49,
    "ONEUP": 50,
    "POWERUP": 51,
    "MIDBOSS_DEFEAT": 52,
    "BOSS_DEFEAT": 53,
    "EXPLOSION": 54,
    "METAL_REFLECT": 55,
    "STAGE9_UNLOCK_STATIC": 27,
    "WARP": 56,
    "ENEMY_JUMP": 57,
    "BOSS_BIG_JUMP": 58,
    "STAGE6_ROCKET": 29,
    "STAGE7_FLOAT_JUMP": 28,
    "BOSS_LAND": 59,
    "GHOST_APPEAR": 60,
    "CHECKPOINT": 61,
    "CONVEYOR_LOOP": 30,
    "CHASER_SLIDE": 62,
    "BOSS_DOOR": 63,
    "TITLE_START": 36,
    "TITLE_SELECT": 37,
    "PAUSE_TOGGLE": 38,
    "ENEMY_DEFEAT": 39,
}

def setup_game_sounds():
    """ゲームで使う効果音を SOUND 31〜63 に本設定する。"""
    data = {
        # ボス/中ボス突進中: 低音ノイズ連打で「ズドドドド」寄せ
        "BOSS_RUSH":   ("c1c1g1c1",        "nnnn",     "7776",     "ffff",     2),
        "BOSS_HIT":    ("c3g2",            "nn",       "76",       "fn",       3),
        # name: (notes, tones, volumes, effects, speed)
        # スプリング通常: トランポリン感のある低めの「ボヨン」
        "SPRING_BOUNCE":("c2g1c2",          "ppp",      "776",      "nnn",      7),
        # スプリング大ジャンプ: ジャンプキー入力時の伸びる「ビヨーン」
        "SPRING_BIG":   ("g1c2g2c3g3",      "ppppp",    "77765",    "nnnnn",    6),
        # 壊せないブロック: 下から叩いた時の鈍い「ゴツッ」音
        "BLOCK_DULL":   ("c1",              "n",        "7",        "f",        6),
        "JUMP":         ("c2d2e2g2",        "pppp",     "7654",     "nnnn",     6),
        "SHOT":         ("c3c3",            "pp",       "74",       "nn",       3),
        # チャージショット: ロックバスター風に、鋭い高音→低音へ落ちる「ビシュッ」寄せ
        "CHARGE_SHOT":  ("c4g3e3c3",        "psnn",     "7775",     "nfff",     3),
        "ARMOR_BREAK":  ("g2e2c2",          "nnn",      "765",      "fff",      5),
        "PLAYER_DAMAGE":("c2g1c1",          "nnn",      "777",      "fff",      6),
        "STOMP":        ("c2g1",            "pp",       "75",       "fn",       4),
        "BLOCK_BREAK":  ("c2c1g1",          "nnn",      "777",      "fff",      3),
        "BLOCK_BUMP":   ("c2",              "n",        "7",        "f",        4),
        "ITEM_APPEAR":  ("c2e2g2c3",        "pppp",     "7654",     "nnnn",     5),
        # コイン取得: 「チャリーン」寄せ。高めの上昇音＋少し余韻。
        "COIN":         ("g3c4e4g4",        "pppp",     "7775",     "nnnn",     3),
        "ONEUP":        ("c3e3g3c4",        "pppp",     "7776",     "nnnn",     6),
        "POWERUP":      ("c2e2g2c3e3",      "ppppp",    "77765",    "nnnnn",    5),
        "MIDBOSS_DEFEAT":("g2e2c2g1",       "nnnn",     "7775",     "ffff",     6),
        "BOSS_DEFEAT":  ("c3g2e2c2g1c1",    "nnnnnn",   "777765",   "ffffff",   7),
        # 爆発: 低音ノイズを何発も重ねて長めの「ボボボンッ！」
        "EXPLOSION":    ("c2c1g1c2c1g1c2c1", "nnnnnnnn", "77777665", "ffffffff", 4),
        "METAL_REFLECT":("g3c3",            "nn",       "76",       "ff",       3),
        # Stage9中ボス無敵解除: テレビ砂嵐のような長めの「ザア〜〜〜〜」
        "STAGE9_UNLOCK_STATIC":("c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c2", "nnnnnnnnnnnnnnnn", "7777777766665554", "ffffffffffffffff", 8),
        # ワープ敵: 音量を上げ、上昇を強めた「フォン！」寄せ
        "WARP":         ("c3g3c4g4",        "ssss",     "7777",     "nnnn",     3),
        "ENEMY_JUMP":   ("c2d2",            "pp",       "65",       "nn",       6),
        # ボス大ジャンプ: 派手で長めのロケット発射「ジュバーン」
        "BOSS_BIG_JUMP":("c1c1g1c2g2c3g3",  "nnnpppp",  "7777775",  "fffnnnn",  5),
        # Stage6ボス専用: 長く噴射するロケット音「シュゴーーーー」
        "STAGE6_ROCKET":("c1c1c1g1g1c2c2g2g2", "nnnnnnnnn", "777777665", "fffffffff", 6),
        # Stage7ボス専用: 音量は明瞭に、音色は空中へ軽く浮かび上がる「フワンッ」
        "STAGE7_FLOAT_JUMP":("c3e3g3c4e4", "pppps", "77776", "nnnnf", 4),
        "BOSS_LAND":    ("c1c1",            "nn",       "77",       "ff",       5),
        "GHOST_APPEAR": ("c2d#2f2g#2",      "ssss",     "7654",     "nnnn",     5),
        # 中間フラッグ: 正解音っぽい「ピンポーン」寄せ
        "CHECKPOINT":   ("g3c4",            "pp",       "77",       "nn",       8),
        # コンベア床: 高いザラつきを避け、低く鈍い「どどどどど」寄せ。
        # ノイズではなく低音トーンを細かく刻み、乗っている間だけ重ねて鳴らす。
        "CONVEYOR_LOOP":("c1c1c1c1c1c1c1c1", "tttttttt", "55554444", "ffffffff", 3),
        # エネミーチェイサー: 方向転換時の擦れ音。さらに2段階下げる。
        "CHASER_SLIDE": ("g2f#2f2e2",       "nnnn",     "4321",     "ffff",     3),
        # ボス部屋接触: 同じザッ系音を高速連続にして「ザザザッ」寄せ
        "BOSS_DOOR":    ("c2g1c1c2g1c1c2g1c1", "nnnnnnnnn", "776776765", "ffnffnfff", 2),
        # タイトル/メニュー系
        "TITLE_START": ("c3e3g3c4",        "pppp",     "7776",     "nnnn",     4),
        "TITLE_SELECT":("c3",              "p",        "6",        "n",        2),
        "PAUSE_TOGGLE":("g2c3",            "pp",       "76",       "nn",       4),
        # 雑魚エネミー撃破: 軽い「ぽふっ」寄せ
        "ENEMY_DEFEAT":("c2g1",            "nn",       "64",       "ff",       5),
    }
    for name, sid in SFX.items():
        # Pyxel の set は (notes, tones, volumes, effects, speed) の順。
        # 以前の版で speed が先頭扱いになり Invalid sound note '5' が出たため、
        # ここでは明示的に分解して渡す。
        notes, tones, volumes, effects, speed = data[name]
        try:
            pyxel.sound(sid).set(notes, tones, volumes, effects, speed)
        except Exception:
            # バージョン差対策：set_* が使える環境では個別設定に切り替える。
            try:
                snd = pyxel.sound(sid)
                snd.set_notes(notes)
                snd.set_tones(tones)
                snd.set_volumes(volumes)
                snd.set_effects(effects)
                snd.speed = speed
            except Exception:
                pass

def is_rect_on_screen(x, y, w=16, h=16, margin=8):
    """ワールド座標の矩形が現在の画面に見えているかを返す。"""
    try:
        g = Game._instance if 'Game' in globals() else None
        cam_x = float(getattr(g, "cam_x", 0)) if g is not None else 0.0
        cam_y = float(getattr(g, "cam_y", 0)) if g is not None else 0.0
        return (x + w >= cam_x - margin and x <= cam_x + SCREEN_W + margin and
                y + h >= cam_y - margin and y <= cam_y + SCREEN_H + margin)
    except Exception:
        return True

def play_sfx(name):
    """効果音再生。未設定/チャンネル競合/環境差があってもゲームを止めない。"""
    try:
        pyxel.play(3, SFX[name])
    except Exception:
        pass

def play_sfx_ch(ch, name):
    """指定チャンネルで効果音再生。同時に重ねたい音用。"""
    try:
        pyxel.play(ch, SFX[name])
    except Exception:
        pass

def play_sfx_at(name, x, y, w=16, h=16, margin=8):
    """画面に映っているものだけ効果音を鳴らす。"""
    try:
        if is_rect_on_screen(float(x), float(y), float(w), float(h), margin):
            play_sfx(name)
    except Exception:
        pass

def play_sfx_at_ch(ch, name, x, y, w=16, h=16, margin=8):
    """画面に映っているものだけ、指定チャンネルで効果音を鳴らす。"""
    try:
        if is_rect_on_screen(float(x), float(y), float(w), float(h), margin):
            play_sfx_ch(ch, name)
    except Exception:
        pass

def play_title_select_sfx():
    """タイトル画面のカーソル移動音。"""
    play_sfx("TITLE_SELECT")

def play_title_start_sfx():
    """タイトル画面からゲーム開始/コンティニューする音。"""
    play_sfx("TITLE_START")

def play_pause_toggle_sfx():
    """ポーズ/ポーズ解除の共通音。"""
    play_sfx("PAUSE_TOGGLE")

def play_enemy_defeat_sfx_at(enemy):
    """雑魚エネミー撃破音。画面内の敵だけ鳴らす。"""
    try:
        play_sfx_at("ENEMY_DEFEAT", enemy.x, enemy.y, enemy.w, enemy.h, margin=16)
    except Exception:
        pass

def play_boss_rush_sfx_at(actor):
    """ボス/中ボスの突進中に鳴らす重めの連続音。画面内だけ鳴らす。"""
    try:
        # 短い音を数フレームおきに重ねて「ズドドドド」感を出す。
        if pyxel.frame_count % 5 == 0:
            play_sfx_at_ch(2, "BOSS_RUSH",
                           actor.x, actor.y,
                           getattr(actor, "w", 32), getattr(actor, "h", 32),
                           margin=24)
    except Exception:
        pass


def play_conveyor_machine_sfx_at(x, y, w=16, h=16):
    """コンベアに乗っている間だけ鳴らす、低く鈍い駆動音。

    「ザッザッ」ではなく、低音トーンを細かく刻んだ
    「どどどどど」に寄せる。
    """
    try:
        if pyxel.frame_count % 18 == 0:
            play_sfx_at_ch(2, "CONVEYOR_LOOP", x, y, w, h, margin=16)
    except Exception:
        pass

def play_boss_defeat_explosion_sfx_at(actor):
    """中ボス/ボス撃破点滅中の連続爆発音。"""
    try:
        if actor is None:
            return
        if pyxel.frame_count % 7 == 0:
            play_sfx_at_ch(2, "EXPLOSION",
                           getattr(actor, "x", 0), getattr(actor, "y", 0),
                           getattr(actor, "w", 32), getattr(actor, "h", 32),
                           margin=32)
    except Exception:
        pass
# ===== SOUND EFFECTS END =====
# ダッシュキー
DASH_KEY  = pyxel.KEY_X
# デバッグプレイ中の無敵ON/OFF切替キー
DEV_INVINCIBLE_KEY = pyxel.KEY_I

# ===== 基本設定 =====
# === ANCHOR: CONFIG_START (OK TO EDIT) ===
SCREEN_W, SCREEN_H = 256, 256

# === ANCHOR: CONFIG_END ===

# === ANCHOR: INPUT_BINDINGS (OK TO EDIT) ===
# ポーズ用キー
PAUSE_KEY = pyxel.KEY_P
STEP_KEY  = pyxel.KEY_S

# ===== Keyboard / Gamepad common input =====
# Keyboard controls remain enabled. Gamepad inputs are added with OR logic.
# Missing gamepad constants are handled safely for compatibility with older Pyxel versions.
def _gamepad_button(name):
    return getattr(pyxel, name, None)

def _gp_btn(name):
    button = _gamepad_button(name)
    return button is not None and pyxel.btn(button)

def _gp_btnp(name):
    button = _gamepad_button(name)
    return button is not None and pyxel.btnp(button)

def input_left():
    return pyxel.btn(pyxel.KEY_LEFT) or _gp_btn("GAMEPAD1_BUTTON_DPAD_LEFT")

def input_right():
    return pyxel.btn(pyxel.KEY_RIGHT) or _gp_btn("GAMEPAD1_BUTTON_DPAD_RIGHT")

def input_left_pressed():
    return pyxel.btnp(pyxel.KEY_LEFT) or _gp_btnp("GAMEPAD1_BUTTON_DPAD_LEFT")

def input_right_pressed():
    return pyxel.btnp(pyxel.KEY_RIGHT) or _gp_btnp("GAMEPAD1_BUTTON_DPAD_RIGHT")

def input_up_pressed():
    return pyxel.btnp(pyxel.KEY_UP) or _gp_btnp("GAMEPAD1_BUTTON_DPAD_UP")

def input_down_pressed():
    return pyxel.btnp(pyxel.KEY_DOWN) or _gp_btnp("GAMEPAD1_BUTTON_DPAD_DOWN")

# Keyboard + Gamepad / virtual-pad configurable action bindings.
# Arrow keys / D-pad remain fixed for movement. Defaults preserve the current layout.
DEFAULT_KEYBOARD_BINDINGS = {
    "JUMP": pyxel.KEY_SPACE,
    "SHOT": pyxel.KEY_Z,
    "DASH": pyxel.KEY_X,
    "START_PAUSE": pyxel.KEY_P,
}
KEYBOARD_BINDINGS = dict(DEFAULT_KEYBOARD_BINDINGS)

DEFAULT_GAMEPAD_BINDINGS = {
    "JUMP": "GAMEPAD1_BUTTON_A",
    "SHOT": "GAMEPAD1_BUTTON_X",
    "DASH": "GAMEPAD1_BUTTON_B",
    "START_PAUSE": "GAMEPAD1_BUTTON_START",
}
GAMEPAD_BINDINGS = dict(DEFAULT_GAMEPAD_BINDINGS)

# Buttons that may be assigned from CONFIG. D-pad is intentionally excluded/fixed.
CONFIGURABLE_GAMEPAD_BUTTONS = [
    "GAMEPAD1_BUTTON_A", "GAMEPAD1_BUTTON_B",
    "GAMEPAD1_BUTTON_X", "GAMEPAD1_BUTTON_Y",
    "GAMEPAD1_BUTTON_LEFTSHOULDER", "GAMEPAD1_BUTTON_RIGHTSHOULDER",
    "GAMEPAD1_BUTTON_LEFTTRIGGER", "GAMEPAD1_BUTTON_RIGHTTRIGGER",
    "GAMEPAD1_BUTTON_BACK", "GAMEPAD1_BUTTON_START",
]

# Keyboard keys accepted by CONFIG. Arrow keys are intentionally excluded/fixed.
# Build the list safely because available Pyxel key constants can vary by version/platform.
_CONFIG_KEY_NAMES = (
    [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    + [str(n) for n in range(10)]
    + ["SPACE", "RETURN", "TAB", "BACKSPACE",
       "LCTRL", "RCTRL", "LSHIFT", "RSHIFT", "LALT", "RALT",
       "COMMA", "PERIOD", "SLASH", "SEMICOLON", "APOSTROPHE",
       "LEFTBRACKET", "RIGHTBRACKET", "BACKSLASH", "MINUS", "EQUAL"]
    + [f"F{n}" for n in range(1, 13)]
)
CONFIGURABLE_KEYBOARD_KEYS = [
    (name, getattr(pyxel, "KEY_" + name))
    for name in _CONFIG_KEY_NAMES
    if hasattr(pyxel, "KEY_" + name)
]

def _bound_key(action):
    return KEYBOARD_BINDINGS.get(action, DEFAULT_KEYBOARD_BINDINGS[action])

def _bound_gp_btn(action):
    return _gp_btn(GAMEPAD_BINDINGS.get(action, DEFAULT_GAMEPAD_BINDINGS[action]))

def _bound_gp_btnp(action):
    return _gp_btnp(GAMEPAD_BINDINGS.get(action, DEFAULT_GAMEPAD_BINDINGS[action]))

def _gamepad_button_short_name(name):
    return str(name).replace("GAMEPAD1_BUTTON_", "")

def _keyboard_key_short_name(key_code):
    for name, code in CONFIGURABLE_KEYBOARD_KEYS:
        if code == key_code:
            return name
    return str(key_code)

def _first_configurable_gamepad_button_pressed():
    for name in CONFIGURABLE_GAMEPAD_BUTTONS:
        if _gp_btnp(name):
            return name
    return None

def _first_configurable_keyboard_key_pressed():
    for name, key_code in CONFIGURABLE_KEYBOARD_KEYS:
        if pyxel.btnp(key_code):
            return key_code
    return None

def input_jump_held():
    return pyxel.btn(_bound_key("JUMP")) or _bound_gp_btn("JUMP")

def input_jump_pressed():
    return pyxel.btnp(_bound_key("JUMP")) or _bound_gp_btnp("JUMP")

def input_shot_held():
    return pyxel.btn(_bound_key("SHOT")) or _bound_gp_btn("SHOT")

def input_shot_pressed():
    return pyxel.btnp(_bound_key("SHOT")) or _bound_gp_btnp("SHOT")

def input_dash():
    return pyxel.btn(_bound_key("DASH")) or _bound_gp_btn("DASH")

def input_decide_pressed():
    # Existing RETURN / A decision remains intact.
    # The configured START/PAUSE button is additionally accepted on title/config screens.
    return pyxel.btnp(pyxel.KEY_RETURN) or _gp_btnp("GAMEPAD1_BUTTON_A")

def input_start_pause_pressed():
    return _bound_gp_btnp("START_PAUSE")

def input_pause_pressed():
    # Keyboard and controller/virtual-pad START/PAUSE are both configurable.
    return pyxel.btnp(_bound_key("START_PAUSE")) or input_start_pause_pressed()

def input_back_to_title_pressed():
    return pyxel.btnp(pyxel.KEY_RETURN) or _gp_btnp("GAMEPAD1_BUTTON_BACK")

def input_dev_invincible_pressed():
    # Keyboard I / Gamepad Y
    return pyxel.btnp(DEV_INVINCIBLE_KEY) or _gp_btnp("GAMEPAD1_BUTTON_Y")

def input_pause_skip_pressed():
    # Keyboard S / Gamepad right shoulder (RB / R1)
    return pyxel.btnp(STEP_KEY) or _gp_btnp("GAMEPAD1_BUTTON_RIGHTSHOULDER")

# 「押しながらダッシュ」に割り当てたキー／ボタンの長押しコマンド。
# このゲームは各種タイマーを60フレーム＝1秒として扱っているため、2秒＝120フレーム。
DASH_HOLD_COMMAND_FRAMES = 2 * 60
# === ANCHOR END ===

# === ANCHOR: DEV_OPTIONS (OK TO EDIT) ===
DEV_START_TIME_SEC = None
DEV_FORCE_LIVES    = None
DEV_BOSS_MIN_SEC   = 45 # None
# デバッグ時間は全ステージ共通。既存の300/100/30/1秒に600秒と時間制限なしを追加。
DEV_TIME_NO_LIMIT = "NO_LIMIT"
DEV_START_TIME_OPTIONS = [300, 600, 100, 30, 1, DEV_TIME_NO_LIMIT]

# ===== Environment change system =====
ENV_CHECK_INTERVAL_FRAMES = 20 * 60
# 各判定タイミングで、まず10%の確率で環境変化そのものが発生する。
ENV_TRIGGER_CHANCE = 0.20
ENV_TYPES = ["NONE", "RAIN", "SNOW", "HEADWIND", "TAILWIND", "FOG", "HEAT", "FIRE", "EARTHQUAKE", "GRAVITY_ANOMALY", "HIGH_GRAVITY"]
ENV_LABELS = {"NONE":"NONE", "RAIN":"RAIN", "SNOW":"SNOW", "HEADWIND":"HEAD WIND",
              "TAILWIND":"TAIL WIND", "FOG":"FOG", "HEAT":"EXTREME HEAT",
              "FIRE":"FIRE", "EARTHQUAKE":"EARTHQUAKE",
              "GRAVITY_ANOMALY":"GRAVITY ANOMALY",
              "HIGH_GRAVITY":"HIGH GRAVITY"}

# ステージごとに自然発生しうる環境。
# デバッグ固定指定はこの表に関係なく、従来どおり全環境を選択可能。
STAGE_ENVIRONMENT_CANDIDATES = {
    1: ("RAIN",),
    2: ("HEADWIND", "TAILWIND"),
    3: ("HEAT", "EARTHQUAKE"),
    4: ("SNOW",),
    5: ("FIRE", "EARTHQUAKE"),
    6: ("FOG", "TAILWIND"),
    7: ("RAIN", "SNOW", "TAILWIND"),
    8: ("FIRE", "EARTHQUAKE"),
    9: ("EARTHQUAKE", "GRAVITY_ANOMALY", "HIGH_GRAVITY"),
}

# Stage9は地震を低確率扱いせず、登録した3種類を均等抽選する。
EQUAL_ENVIRONMENT_SELECTION_STAGES = (9,)

# 地震が候補に含まれる場合、環境変化発生後の抽選で20%。
# 残り80%は、同ステージの地震以外の候補へ均等配分する。
EARTHQUAKE_SELECTION_CHANCE = 0.20
EARTHQUAKE_WARNING_FRAMES = 120

# 重力異常（自然発生はStage9のみ。DEV_MENUでは全ステージ選択可能）
# 通常時の物理値は変更せず、下記倍率は環境変化中だけ参照する。
GRAVITY_ANOMALY_JUMP_MULT = 0.78
GRAVITY_ANOMALY_GRAVITY_MULT = 0.50
GRAVITY_ANOMALY_MOVE_MULT = 0.65

# 高重力（自然発生はStage9のみ。DEV_MENUでは全ステージ選択可能）
# 横移動・ジャンプ初速は通常の80%。重力と最大落下速度を増やして落下を速くする。
HIGH_GRAVITY_MOVE_MULT = 0.80
HIGH_GRAVITY_JUMP_MULT = 0.80
HIGH_GRAVITY_GRAVITY_MULT = 1.25
HIGH_GRAVITY_MAX_FALL_MULT = 1.25
HIGH_GRAVITY_ITEM_FALL_MULT = 1.10
# === ANCHOR END ===

# ===== 物理 =====
# === ANCHOR: PHYSICS (DO NOT EDIT) ===
FLOOR_Y = 208
GRAVITY = 0.5
#JUMP_VY = -7.5

SPRING_JUMP_MULT = 2.0  # 通常ジャンプの約2倍の高さ
JUMP_VY = -9.0
#JUMP_VY = -12.0
MOVE_SPD = 2
SPRING_ANIM_PERIOD = 12      # 交互表示の周期（小さいほど速い）
SPRING_PRESS_FRAMES = 8      # 踏んだ瞬間にSPRING2を出すフレーム数
# === ANCHOR END ===


# ===== 入力取りこぼし改善(コヨーテ/バッファ) =====
# === ANCHOR: INPUT_TUNING (OK TO EDIT) ===
COYOTE_FRAMES = 6
JUMPBUF_FRAMES = 6
# === Jump 2x (range & height) helpers ===
# 高さ2倍 → v0 を sqrt(2) 倍
# 距離2倍 → 空中の水平速度も sqrt(2) 倍
# --- Mario-like variable jump tuning (multipliers only; GRAVITY/JUMP_VY不変更) ---
JUMP_HOLD_GRAV_MULT = 0.9   # ジャンプボタン押し続け中(上昇中)の重力係数(ふわっと)
JUMP_RELEASE_GRAV_MULT = 1.6# ボタン離した(上昇中)ときの重力係数(ストン)
FALL_GRAV_MULT = 1.2        # 下降中の重力係数(少し重めにして気持ちよく落とす)
JUMP_CUT_VY = -3.6          # ボタン離した瞬間、上昇が強すぎるときの上限(短跳び用)
MAX_FALL_SPEED = 7.0        # 終端落下速度の上限(落下しすぎ防止)
APEX_HANG_FRAMES = 3        # 頂点付近のふわっと感(重力を少し軽くするフレーム数)
SQRT2 = 1.41421356237
AIR_X_MULT = SQRT2          # プレイヤー空中時の水平速度倍率
HOPPER_AIR_X_MULT = SQRT2   # ホッパー空中時の水平速度倍率
JUMP_VY_MULT = SQRT2        # ジャンプ初速(縦)倍率

AIR_X_MULT = 2.0         # プレイヤー:空中時のX移動を2倍
HOPPER_AIR_X_MULT = 2.0  # ホッパー:空中時のX移動を2倍
JUMP_PWR_MULT = 2.0      # ジャンプ初速(Y)を2倍
# --- Dash ---
# Xキーで常時ダッシュ(地上/空中ともに最終速度をさらに乗算)
DASH_X_MULT = 1.3
# 充填ショット:必要ホールド時間(約2秒@30fps)
CHARGE_NEED_FRAMES = 60

# === ANCHOR END ===

# --- Power-up tuning (size32 / armor>0 のとき適用) ---
ATTACK_MULT_POWERED = 2.0
# 距離/高さともに1.1倍にするための係数: 縦初速・空中の水平速度を √1.1 倍
POWER_JUMP_FACTOR = 1.048808848  # sqrt(1.1)

# ===== タイル種別 =====
# === ANCHOR: TILE_TYPES (DO NOT EDIT) ===
EMPTY = 0
SOLID = 1       # 地形(床)
GOAL = 2
CHECKPOINT = 3
TILE_BLOCK = 4  # 乗れる通常ブロック
TILE_BREAK = 5  # 下から叩くと壊れる
TILE_ITEM  = 6  # 下から叩くとアイテム出現(壊れる)
TILE_GHOST = 7  # 隠し:点滅足場(出現/消失)
TILE_DOOR  = 8  # ボス部屋へ移動する扉
TILE_COIN  = 9  # コイン(100点)
# === ANCHOR END ===

# === ANCHOR: TILE_TYPES_EXTRA (OK TO EDIT) ===
# 追加タイル（当たり判定用）
#  - TILE_KILL   : 踏むと即ミスになる床（トゲ等の想定）
#  - TILE_SPRING : 踏むと上方向へ強制ジャンプする床（バネ）
TILE_KILL   = 10
TILE_SPRING = 11
# === ANCHOR END ===

# === ANCHOR: UTILS (DO NOT EDIT) ===
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def rect_to_tiles(x, y, w, h):
    left = int(x // TILE)
    right = int((x + w - 1) // TILE)
    top = int(y // TILE)
    bottom = int((y + h - 1) // TILE)
    return left, right, top, bottom

def aabb(ax, ay, aw, ah, bx, by, bw, bh):
    return (ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah)

def tile_at(level, TILES_X, TILES_Y, tx, ty):
    if tx < 0 or tx >= TILES_X:
        return SOLID
    if ty >= TILES_Y:
        return EMPTY
    if ty < 0:
        return SOLID
    return level[ty][tx]

def tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx, ty):
    tid = tile_at(level, TILES_X, TILES_Y, tx, ty)
    if tid == TILE_GHOST:
        return (pyxel.frame_count // 30) % 2 == 0
    return tid in (SOLID, TILE_BLOCK, TILE_BREAK, TILE_ITEM)

# ===== 踏み付け判定(上半分&ゆるい縁) =====
# 8px→16px化に合わせ、マージン/スロップを倍相当に
def can_stomp(player, enemy, top_ratio=0.5, x_margin=8, y_slop=4):
    if player.vy <= 0:
        return False
    px_l = player.x
    px_r = player.x + player.w
    py_f = player.y + player.h
    ex_l = enemy.x - x_margin
    ex_r = enemy.x + enemy.w + x_margin
    ey_t = enemy.y
    ey_s = enemy.y + enemy.h * top_ratio
    return (px_r > ex_l and px_l < ex_r) and (py_f >= ey_t - y_slop and py_f <= ey_s + y_slop)
# === ANCHOR END ===

# ===== 動くブロック =====
# === ANCHOR: PLATFORM (DO NOT EDIT) ===

class MovingPlatform:
    def __init__(self, x, y, w, left, right, spd=1, conveyor_dir_right=None, conveyor_spd=0):
        # すべて16グリッドにスナップ（呼び出し側のタプルは16の倍数を保証）
        self.x = x
        self.y = y
        self.w = max(TILE, w)
        self.h = TILE
        self.left = left
        self.right = right
        self.spd = spd
        # MARK_CONVEYOR(32,16) が近くにある場合、動く床にもコンベア効果を付ける
        self.conveyor_dir_right = conveyor_dir_right
        self.conveyor_spd = abs(conveyor_spd) if conveyor_dir_right is not None else 0
        self.dx_last = 0
        self.dy_last = 0

    def update(self):
        prev_x, prev_y = self.x, self.y
        self.x += self.spd
        if self.x < self.left or self.x + self.w > self.right:
            self.spd *= -1
            self.x += self.spd
        self.dx_last = self.x - prev_x
        self.dy_last = self.y - prev_y

    def draw(self):
        # 背景やカメラは触らず、床そのものだけ描画
        # pyxel.rect(self.x, self.y, self.w, self.h, 5)
        draw_platform_span(self.x, self.y, self.w, TILE, "MOVE_H")

# ===== アイテム =====
# === ANCHOR: ITEM (DO NOT EDIT) ===
class Item:
    # type: "1UP" | "BIGPTS" | "POWER" | "ARMOR"
    def __init__(self, x, y, itype):
        self.x = x; self.y = y
        self.w = 16; self.h = 16
        self.vy = -2.0
        self.type = itype
        self.alive = True

    def update(self):
        game = Game._instance if 'Game' in globals() else None
        item_gravity = 0.1
        if game and getattr(game, "environment", "NONE") == "HIGH_GRAVITY":
            item_gravity *= HIGH_GRAVITY_ITEM_FALL_MULT
        self.vy += item_gravity
        self.y += self.vy

        # Stage9 は縦8画面(2048px)なので、通常の WORLD_H(256px) 判定だと
        # スタート画面より下で出したアイテムが即座に消えてしまう。
        # 現在ステージの実ワールド高さを使って、全フィールドでアイテムを生存させる。
        g = Game._instance if 'Game' in globals() else None
        try:
            world_h = stage_world_h(getattr(g, "stage", 1)) if g is not None else WORLD_H
        except Exception:
            world_h = WORLD_H

        if self.y > world_h + 32:
            self.alive = False

    def draw(self):
        u, v = ITEM_UV.get(self.type, (0, 240))
        x, y = int(self.x), int(self.y)
        # 全場面で視認性を保つため、常時1pxの黒い輪郭影を描く。
        if True:
            try:
                for col in range(1, 16):
                    pyxel.pal(col, 0)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    pyxel.blt(x + dx, y + dy, 0, u, v, self.w, self.h, 0)
            finally:
                pyxel.pal()
        pyxel.blt(x, y, 0, u, v, self.w, self.h, 0)
# === ANCHOR END ===

class Stage9Gem:
    """Stage9-only stationary collectible gem. Never expires until collected."""
    def __init__(self, gem_id, x, y):
        self.gem_id = str(gem_id)
        self.x = float(x)
        self.y = float(y)
        self.w = 16
        self.h = 16
        self.alive = True

    def update(self):
        # Static in midair by design. No lifetime/gravity.
        return

    def draw(self):
        x, y = int(self.x), int(self.y)
        # 16x16 translucent-crystal impression: dark edge + cyan facets.
        pts = [(x+8,y), (x+14,y+5), (x+12,y+12), (x+8,y+15), (x+4,y+12), (x+2,y+5)]
        # black silhouette/outline first
        pyxel.tri(x+8,y, x+14,y+5, x+8,y+15, 0)
        pyxel.tri(x+8,y, x+8,y+15, x+2,y+5, 0)
        # transparent-looking faceted body
        pyxel.tri(x+8,y+1, x+13,y+5, x+8,y+13, 12)
        pyxel.tri(x+8,y+1, x+8,y+13, x+3,y+5, 6)
        pyxel.tri(x+8,y+4, x+12,y+6, x+8,y+12, 5)
        pyxel.tri(x+8,y+4, x+8,y+12, x+4,y+6, 13)
        pyxel.line(x+3,y+5, x+13,y+5, 7)
        pyxel.line(x+8,y+1, x+8,y+13, 7)
        # subtle mirror-like moving gleam
        phase = (pyxel.frame_count // 5 + (hash(self.gem_id) & 7)) % 12
        if phase < 6:
            gx = x + 5 + phase
            gy = y + 3 + phase // 2
            if gx < x + 13 and gy < y + 11:
                pyxel.pset(gx, gy, 7)
                if phase in (1, 2, 3):
                    pyxel.pset(max(x+2, gx-1), gy, 10)
        if (pyxel.frame_count + (hash(self.gem_id) & 31)) % 48 < 3:
            pyxel.pset(x+3, y+2, 7)
            pyxel.pset(x+2, y+3, 7)
            pyxel.pset(x+4, y+3, 7)
            pyxel.pset(x+3, y+4, 7)

class MovingPlatformV:
    def __init__(self, x, y, h, top, bottom, spd=1, conveyor_dir_right=None, conveyor_spd=0):

        self.x = snap16(x); self.y = snap16(y); self.w = TILE
        self.h = max(TILE, snap16(h))
        self.top = snap16(top); self.bottom = snap16(bottom)
        self.spd = spd
        # MARK_CONVEYOR(32,16) が近くにある場合、縦動く床にもコンベア効果を付ける
        self.conveyor_dir_right = conveyor_dir_right
        self.conveyor_spd = abs(conveyor_spd) if conveyor_dir_right is not None else 0
        self.dx_last = 0
        self.dy_last = 0
    def update(self):
        prev_x, prev_y = self.x, self.y
        self.y += self.spd
        if self.y < self.top or self.y + self.h > self.bottom:
            self.spd *= -1
            self.y += self.spd
        self.dx_last = self.x - prev_x
        self.dy_last = self.y - prev_y
    def draw(self):
        # pyxel.rect(self.x, self.y, self.w, self.h, 3)
        draw_platform_span(self.x, self.y, TILE, self.h, "MOVE_V")

# === ANCHOR: EXTRA_PLATFORMS (OK TO EDIT) ===
# === ANCHOR: EXTRA_PLATFORMS (OK TO EDIT) ===
def _kind_at_tm2(stage_index, tx, ty):
    """TM2優先→無ければAIR。UV→kind 変換済みの名前を返す。"""
    try:
        tm = pyxel.tilemap(2)
        tm.imgsrc = 1
    except Exception:
        try:
            tm = pyxel.tilemap(1)
            tm.imgsrc = 1
        except Exception:
            return "AIR"
    cell = tm.pget(tx*2, stage_index*32 + ty*2)  # 8pxセルの左上を代表に
    u, v = cell[0]*8, cell[1]*8
    return UV_TO_KIND.get((_snap8(u, v)), "AIR")

def _scan_near_marker_count(stage_index, marker_kind, is_h, base_tx, base_ty, length):
    """床本体の近くに置いたマーカー数を数える。

    エディタでは床本体(MOVE_H/MOVE_V/AUTO)と同じマスに速度マーカーを置けないため、
    本体の上下左右1タイルまでを有効範囲にする。
    - 横床/AUTO: 本体の左1〜右1、上1〜下1
    - 縦床     : 本体の上1〜下1、左1〜右1
    """
    count = 0
    if is_h:
        x0 = max(0, base_tx - 1)
        x1 = base_tx + length
        y0 = max(0, base_ty - 1)
        y1 = base_ty + 1
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if _kind_at_tm2(stage_index, tx, ty) == marker_kind:
                    count += 1
    else:
        x0 = max(0, base_tx - 1)
        x1 = base_tx + 1
        y0 = max(0, base_ty - 1)
        y1 = base_ty + length
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if _kind_at_tm2(stage_index, tx, ty) == marker_kind:
                    count += 1
    return count

def _scan_speed_hint(stage_index, is_h, base_tx, base_ty, length):
    """MARK_P(48,48) の個数 × 0.5 を速度加算。既定1.0。"""
    count = _scan_near_marker_count(stage_index, "MARK_P", is_h, base_tx, base_ty, length)
    return 1.0 + 0.5 * count

def _count_marker_line(stage_index, tx, ty, step):
    """指定位置から step 方向へ、連続する MARK_CONVEYOR 数を数える。"""
    count = 0
    tx += step
    while 0 <= tx < 256 and _kind_at_tm2(stage_index, tx, ty) == "MARK_CONVEYOR":
        count += 1
        tx += step
    return count

def _scan_conveyor_hint(stage_index, is_h, base_tx, base_ty, length):
    """MARK_CONVEYOR(32,16) でコンベア効果を指定する。

    直感的な指定方式：
    - コンベア/動く床本体の真下または真上に MARK_CONVEYOR を1個置くと、
      その床をコンベア対象にする。単独なら右向き・速度1。
    - その基準マーカーの右へ連続して置くと、右向きのまま速度アップ。
      例: 基準+右1個 => 右向き速度2。
    - その基準マーカーの左へ連続して置くと、左向きに変更。
      例: 基準+左1個 => 左向き速度1、基準+左2個 => 左向き速度2。

    戻り値: (dir_right, speed, count)
    - count=0: コンベア指定なし
    """
    candidates = []

    if is_h:
        # 横方向の床/AUTOは、床本体の各タイルの真上/真下だけを基準点にする。
        for ty in (base_ty + 1, base_ty - 1):
            if not (0 <= ty < 256):
                continue
            for tx in range(base_tx, base_tx + length):
                if _kind_at_tm2(stage_index, tx, ty) != "MARK_CONVEYOR":
                    continue
                left_count = _count_marker_line(stage_index, tx, ty, -1)
                right_count = _count_marker_line(stage_index, tx, ty, 1)
                total = 1 + left_count + right_count
                if left_count > 0 and right_count == 0:
                    candidates.append((False, float(max(1, left_count)), total))
                elif right_count > 0 and left_count == 0:
                    candidates.append((True, float(1 + right_count), total))
                elif left_count > 0 and right_count > 0:
                    # 両側に置かれていた場合は、長い側を優先。並びが同数なら右優先。
                    if left_count > right_count:
                        candidates.append((False, float(max(1, left_count)), total))
                    else:
                        candidates.append((True, float(1 + right_count), total))
                else:
                    candidates.append((True, 1.0, total))
    else:
        # 縦移動床でも、各床タイルの真上/真下に置いた横並びマーカーで
        # コンベア効果を付けられるようにする。
        for body_ty in range(base_ty, base_ty + length):
            for ty in (body_ty + 1, body_ty - 1):
                if not (0 <= ty < 256):
                    continue
                tx = base_tx
                if _kind_at_tm2(stage_index, tx, ty) != "MARK_CONVEYOR":
                    continue
                left_count = _count_marker_line(stage_index, tx, ty, -1)
                right_count = _count_marker_line(stage_index, tx, ty, 1)
                total = 1 + left_count + right_count
                if left_count > 0 and right_count == 0:
                    candidates.append((False, float(max(1, left_count)), total))
                elif right_count > 0 and left_count == 0:
                    candidates.append((True, float(1 + right_count), total))
                elif left_count > 0 and right_count > 0:
                    if left_count > right_count:
                        candidates.append((False, float(max(1, left_count)), total))
                    else:
                        candidates.append((True, float(1 + right_count), total))
                else:
                    candidates.append((True, 1.0, total))

    if not candidates:
        return None, 0.0, 0

    # 1つの床に複数指定があった場合は、もっとも速い指定を採用。
    # 同速ならマーカー総数が多いものを優先。
    dir_right, speed, count = max(candidates, key=lambda v: (v[1], v[2]))
    return dir_right, speed, count

def _scan_bound(stage_index, is_h, base_tx, base_ty, length):
    """MARK_L と MARK_R で往復範囲を検出。無ければ ±3タイル(48px)。"""
    if is_h:
        ty = base_ty
        left = right = None
        # 左側へ
        tx = base_tx - 1
        while tx >= 0 and tx >= base_tx - 24:
            k = _kind_at_tm2(stage_index, tx, ty)
            if k == "MARK_L": left = tx; break
            tx -= 1
        # 右側へ
        tx = base_tx + length
        while tx < 256 and tx <= base_tx + length + 24:
            k = _kind_at_tm2(stage_index, tx, ty)
            if k == "MARK_R": right = tx; break
            tx += 1
        if left is None:  left  = base_tx - 3
        if right is None: right = base_tx + length + 3
        return left * TILE, right * TILE
    else:
        tx = base_tx
        top = bottom = None
        # 上へ
        ty = base_ty - 1
        while ty >= 0 and ty >= base_ty - 24:
            k = _kind_at_tm2(stage_index, tx, ty)
            if k == "MARK_A": top = ty; break
            ty -= 1
        # 下へ
        ty = base_ty + length
        while ty < 256 and ty <= base_ty + length + 24:
            k = _kind_at_tm2(stage_index, tx, ty)
            if k == "MARK_U": bottom = ty; break
            ty += 1
        if top is None:    top    = base_ty - 3
        if bottom is None: bottom = base_ty + length + 3
        return top * TILE, bottom * TILE

def parse_editor_platforms(stage, TILES_X, TILES_Y):
    """TM2から可動床(AUTO/MOVE_H/MOVE_V)を抽出してインスタンスを返す。"""
    plats = []
    stage_index = tilemap_stage_index(stage)

    # 横可動 / 自走：各行を走査して連続 run を固める
    for ty in range(TILES_Y):
        tx = 0
        while tx < TILES_X:
            k = _kind_at_tm2(stage_index, tx, ty)
            if k in ("MOVE_H", "AUTO"):
                start = tx
                while tx < TILES_X and _kind_at_tm2(stage_index, tx, ty) == k:
                    tx += 1
                length = tx - start
                w = max(TILE, length * TILE)
                x = start * TILE
                y = ty * TILE
                # left, right は従来通りスキャンするが、AUTOは往復しない（参考用）
                left, right = _scan_bound(stage_index, True, start, ty, length)
                spd = _scan_speed_hint(stage_index, True, start, ty, length)
                conv_dir, conv_spd, conv_count = _scan_conveyor_hint(stage_index, True, start, ty, length)

                if k == "AUTO":
                    # MARK_CONVEYOR(32,16) の個数で向き・速度を決める。
                    # 無い場合は従来どおり MARK_R/MARK_L を見て、無ければ右向き。
                    if conv_count > 0:
                        dir_right = conv_dir
                        auto_spd = conv_spd
                    else:
                        auto_spd = spd
                        dir_right = True
                        for t in range(start + length, min(start + length + 24, TILES_X)):
                            if _kind_at_tm2(stage_index, t, ty) == "MARK_R":
                                dir_right = True; break
                        for t in range(start - 1, max(start - 24, -1), -1):
                            if _kind_at_tm2(stage_index, t, ty) == "MARK_L":
                                dir_right = False; break
                    plats.append(Conveyor(x, y, w, dir_right, auto_spd))
                else:
                    plats.append(MovingPlatform(x, y, w, left, right, spd, conv_dir, conv_spd))

                # ★ここで掃除（本体ラン＋マーカー）
                #_clear_tm1_run(stage_index, start, ty, length, is_h=True)
                #_clear_tm1_markers(stage_index, left//TILE, ty, right//TILE, ty)
            else:
                tx += 1

    # 縦可動：各列を走査して連続 run を固める
    for tx in range(TILES_X):
        ty = 0
        while ty < TILES_Y:
            k = _kind_at_tm2(stage_index, tx, ty)
            if k == "MOVE_V":
                start = ty
                while ty < TILES_Y and _kind_at_tm2(stage_index, tx, ty) == "MOVE_V":
                    ty += 1
                length = ty - start
                h = max(TILE, length * TILE)
                x = tx * TILE
                y = start * TILE
                top, bottom = _scan_bound(stage_index, False, tx, start, length)
                spd = _scan_speed_hint(stage_index, False, tx, start, length)
                conv_dir, conv_spd, conv_count = _scan_conveyor_hint(stage_index, False, tx, start, length)
                plats.append(MovingPlatformV(x, y, h, top, bottom, spd, conv_dir, conv_spd))

                # ★掃除
                #_clear_tm1_run(stage_index, tx, start, length, is_h=False)
                #_clear_tm1_markers(stage_index, tx, top//TILE, tx, bottom//TILE)

            else:
                ty += 1

    return plats
# === ANCHOR END ===
class CrumblePlatform:
    def __init__(self, x, y, w=TILE, h=6, delay_frames=18, fall_g=0.25):
        self.x = x; self.y = y; self.w = w; self.h = h
        self.delay_frames = delay_frames; self.fall_g = fall_g
        self.state = 0; self.timer = 0; self.vy = 0.0
        self.dx_last = 0; self.dy_last = 0
    def _player_on_top(self):
        g = Game._instance
        if not g or not g.player or not g.player.alive: return False
        p = g.player
        return (p.x + p.w > self.x and p.x < self.x + self.w and
                p.y + p.h >= self.y - 1 and p.y + p.h <= self.y + 6 and
                p.vy >= 0)
    def update(self):
        prev_y = self.y
        if self.state == 0:
            if self._player_on_top():
                self.state = 1; self.timer = self.delay_frames
        elif self.state == 1:
            self.timer -= 1
            if self.timer <= 0:
                self.state = 2; self.vy = 0.0
        elif self.state == 2:
            self.vy += self.fall_g; self.y += self.vy
            if self.y > WORLD_H: self.state = 3
        self.dx_last = 0; self.dy_last = self.y - prev_y
    def draw(self):
        if self.state == 3: return
        y = self.y
        if self.state == 1 and (pyxel.frame_count // 3) % 2 == 0: y += 1
        pyxel.rect(self.x, y, self.w, self.h, 12)

class AutoPlatform(MovingPlatform):
    def __init__(self, x, y, w, left, right, spd=1.5):
        super().__init__(x, y, w, left, right, spd)
        self._reverse_timer = 0; self._prefer_dir = 1
    def update(self):
        prev_x = self.x
        if self._reverse_timer <= 0 and self.spd * self._prefer_dir > 0:
            import random as _rnd
            if _rnd.random() < 0.004:
                self._reverse_timer = _rnd.randint(24, 60)
                self.spd = -abs(self.spd)
        if self._reverse_timer > 0:
            self._reverse_timer -= 1
            if self._reverse_timer == 0:
                self.spd = abs(self.spd) * self._prefer_dir
        self.x += self.spd
        if self.x < self.left or self.x + self.w > self.right:
            self.spd *= -1; self.x += self.spd
        self.dx_last = self.x - prev_x; self.dy_last = 0
    def draw(self):
        pyxel.rect(self.x, self.y, self.w, self.h, 10)
# === ANCHOR END ===

# === ANCHOR: PLATFORM_SPRITES (OK TO EDIT) ===
# プラットフォーム用のタイルUV（エディタUVに合わせる）
PLATFORM_UV = {
    "MOVE_H": (80, 0),   # 横可動の見た目
    "MOVE_V": (96, 0),   # 縦可動の見た目
    "AUTO"  : (128, 0),  # コンベアの見た目
}
 
# アイテム用のタイルUV（エディタUVに合わせる）
# ※ここの(U, V)は「sekka.pyxres」で実際に置いている座標に合わせて直してね
ITEM_UV = {
    "POWER" : (208, 0),   # パワーアップ
    "ARMOR" : (224, 0),  # アーマー
    "BIGPTS": (192, 0),  # 大得点
    "1UP"   : (176, 0),  # 1UP
}



def parse_editor_enemies(stage, TILES_X, TILES_Y, level):
    """TM2から敵(E_*)を抽出してインスタンスを返す。
    使い方(推奨):
      - TM2に E_WALKER / E_HOPPER / E_FLYER / E_SHOOTER を配置
      - 同じ行に MARK_L / MARK_R を置くと、その区間が左右移動範囲になる
        (無ければデフォルトで x±48)
    """
    enemies = []
    stage_index = tilemap_stage_index(stage)

    def _range_from_markers(tx, ty, default_px=48):
        # 左: 近い MARK_L を探す
        lt = tx
        while lt > 0 and _kind_at_tm2(stage_index, lt, ty) != "MARK_L":
            lt -= 1
        left_px = (lt * TILE) if _kind_at_tm2(stage_index, lt, ty) == "MARK_L" else (tx * TILE - default_px)

        # 右: 近い MARK_R を探す
        rt = tx
        while rt < TILES_X - 1 and _kind_at_tm2(stage_index, rt, ty) != "MARK_R":
            rt += 1
        right_px = (rt * TILE) if _kind_at_tm2(stage_index, rt, ty) == "MARK_R" else (tx * TILE + default_px)

        # 念のため入れ替わりを補正
        if right_px < left_px:
            left_px, right_px = right_px, left_px
        return left_px, right_px

    def _has_lr_markers(tx, ty):
        """同じ行に MARK_L / MARK_R が両方ある場合だけ、追尾範囲指定ありとする。"""
        has_l = False
        sx = tx
        while sx >= 0:
            if _kind_at_tm2(stage_index, sx, ty) == "MARK_L":
                has_l = True
                break
            sx -= 1
        has_r = False
        sx = tx
        while sx < TILES_X:
            if _kind_at_tm2(stage_index, sx, ty) == "MARK_R":
                has_r = True
                break
            sx += 1
        return has_l and has_r

    def _vertical_range_from_markers(tx, ty, default_px=48):
        """フライヤー用の上下移動範囲。
        TM2で同じ列に MARK_A(上端) / MARK_U(下端) の両方を置いた時だけ、
        上下往復モードにする。

        片方または両方が無い場合は None を返し、
        従来の「ゆっくり下にジグザグ降下」モードを維持する。
        """
        tt = ty
        while tt > 0 and _kind_at_tm2(stage_index, tx, tt) != "MARK_A":
            tt -= 1
        has_top = (_kind_at_tm2(stage_index, tx, tt) == "MARK_A")

        bt = ty
        while bt < TILES_Y - 1 and _kind_at_tm2(stage_index, tx, bt) != "MARK_U":
            bt += 1
        has_bottom = (_kind_at_tm2(stage_index, tx, bt) == "MARK_U")

        if not (has_top and has_bottom):
            return None, None

        top_px = tt * TILE
        bottom_px = bt * TILE
        if bottom_px < top_px:
            top_px, bottom_px = bottom_px, top_px
        return top_px, bottom_px

    def _speed_mult_from_p(ty, left_px, right_px):
        """同一行(ty)の MARK_P 数で速度倍率を決める。倍率=1.0+0.5*count"""
        tx0 = max(0, int(left_px // TILE))
        tx1 = min(TILES_X - 1, int((right_px - 1) // TILE))
        count = 0
        for tx in range(tx0, tx1 + 1):
            if _kind_at_tm2(stage_index, tx, ty) == "MARK_P":
                count += 1
        return 1.0 + 0.5 * count


    def _top_surface_y_near(x, h, ty_hint):
        """TM2で置いた行(ty_hint)付近から下方向に探して、最初の地面表面に吸着する。
        同じX上に上段の足場があっても、意図した高さ付近を優先できる。
        """
        tx = int(x // TILE)
        start_ty = max(0, ty_hint - 2)
        for ty2 in range(start_ty, TILES_Y):
            if tile_is_ground_for_enemy(level.level, TILES_X, TILES_Y, tx, ty2):
                if ty2 - 1 >= 0 and not tile_is_ground_for_enemy(level.level, TILES_X, TILES_Y, tx, ty2 - 1):
                    return ty2 * TILE - h
        # 見つからなければ従来通り（最上段の床）
        try:
            return level.top_surface_y(x, h)
        except Exception:
            return ty_hint * TILE - h
    for ty in range(TILES_Y):
        for tx in range(TILES_X):
            k = _kind_at_tm2(stage_index, tx, ty)
            if k not in (
                "E_WALKER", "E_HOPPER", "E_FLYER", "E_SHOOTER",
                "E_STOMP_WALKER", "E_IMMUNE_WALKER",
                "E_WARP", "E_CHASER_WALKER", "E_SPLIT_FLYER", "E_AIM_SHOOTER",
                "E_MISSILE_L", "E_MISSILE_R", "E_MISSILE_U", "E_MISSILE_D"
            ):
                continue

            x = tx * TILE
            # y は「TM2で置いた行(ty)」付近の地面に吸着（上段の足場に吸われるのを防ぐ）
            if k in ("E_WALKER", "E_HOPPER", "E_SHOOTER", "E_STOMP_WALKER", "E_IMMUNE_WALKER",
                     "E_WARP", "E_CHASER_WALKER", "E_AIM_SHOOTER"):
                y = _top_surface_y_near(x, 16, ty)
            else:
                y = ty * TILE

            left, right = _range_from_markers(tx, ty, default_px=48)
            mult = _speed_mult_from_p(ty, left, right)

            if k == "E_WALKER":
                enemies.append(Walker(x, y, left, right, spd=1.0 * mult))
            elif k == "E_HOPPER":
                enemies.append(Hopper(x, y, left, right, spd=0.3 * mult))
            elif k == "E_FLYER":
                # エディタ配置フライヤーは、プレイヤーが近づくまで待機させる。
                # 左右は MARK_L/MARK_R、上下は MARK_A(上端: IMAGE 2,6) / MARK_U(下端: IMAGE 4,6) で指定。
                top, bottom = _vertical_range_from_markers(tx, ty, default_px=48)
                enemies.append(Flyer(x, y, left, right, spd=1.0 * mult, active=False, top=top, bottom=bottom))
            elif k == "E_SHOOTER":
                enemies.append(Shooter(x, y))
            elif k == "E_STOMP_WALKER":
                enemies.append(StompDamageWalker(x, y, left, right, spd=1.0 * mult))
            elif k == "E_IMMUNE_WALKER":
                enemies.append(NormalShotImmuneWalker(x, y, left, right, spd=1.0 * mult))
            elif k == "E_WARP":
                enemies.append(WarpEnemy(x, y, hp=2))
            elif k == "E_CHASER_WALKER":
                enemies.append(ChaserWalker(x, y, spd=2.5 * mult, hp=2, left=left, right=right, bounded=_has_lr_markers(tx, ty)))
            elif k == "E_SPLIT_FLYER":
                top, bottom = _vertical_range_from_markers(tx, ty, default_px=48)
                enemies.append(SplitImmortalFlyer(x, y, left, right, spd=1.0 * mult, active=False, top=top, bottom=bottom))
            elif k == "E_AIM_SHOOTER":
                enemies.append(AimShooter(x, y, bullet_speed=4.5, hp=3))
            elif k == "E_MISSILE_L":
                enemies.append(MissileEnemy(x, y, dir="L", speed=2.0 * mult))
            elif k == "E_MISSILE_R":
                # ステージ5専用ギミック：
                # 指定したTM2エディタ座標(8px単位)の右進行ミサイルだけ、
                # プレイヤーの左足元が指定TM2エディタ座標へ来た時点で起動する。
                #
                # ※ここでの tx/ty は16px単位なので、
                #   ミサイル設置座標は Pyxelエディタの8px座標を /2 して比較する。
                # ※ trigger_cells は「エディタ表示そのまま」の8px座標で持つ。
                trigger_cells = None
                trigger_x = None
                sy = tilemap_v8_row(stage)

                # リクエスト：
                # TM2エディタ座標(138,206)に置いた右向きミサイルは、
                # プレイヤーがTM2エディタX座標138へ到達したら起動する。
                # Y座標は見ず、X軸だけで判定する。
                if tx == 138 // 2 and ty == (206 - sy) // 2:
                    trigger_x = 138

                # リクエスト：
                # TM2エディタ座標
                # (168,192)(168,194)(168,196)(168,198)
                # (168,200)(168,202)(168,204)(168,206)
                # に置いた右向きミサイルは、プレイヤーが
                # TM2エディタX座標176へ到達し、かつY座標が208より上方なら起動する。
                # ※ tx/ty は16px単位なので、エディタ8px座標は /2 して比較する。
                if tx == 168 // 2 and ty in {
                    (192 - sy) // 2, (194 - sy) // 2, (196 - sy) // 2, (198 - sy) // 2,
                    (200 - sy) // 2, (202 - sy) // 2, (204 - sy) // 2, (206 - sy) // 2,
                }:
                    trigger_x = 176
                    trigger_y_lt = 208
                else:
                    trigger_y_lt = None

                if int(stage) == 5:
                    if tx == 148 // 2 and ty == (144 - sy) // 2:
                        trigger_cells = [(158, 142), (158, 144), (158, 146)]

                    elif tx == 104 // 2 and ty == (144 - sy) // 2:
                        # リクエスト：
                        # ミサイル場所 TM2(104,144)
                        # プレイヤー条件 TM2(112,146) ピンポイント
                        trigger_cells = [(112, 146)]

                    elif tx == 14 // 2 and ty == (130 - sy) // 2:
                        trigger_cells = [(22, 130), (22, 132)]

                    elif tx == 112 // 2 and ty == (154 - sy) // 2:
                        trigger_cells = [(120, 150), (120, 152), (120, 154), (120, 156)]

                enemies.append(MissileEnemy(x, y, dir="R", speed=2.0 * mult, trigger_tm2_cells=trigger_cells, trigger_tm2_x=trigger_x, trigger_tm2_y_lt=trigger_y_lt))
            elif k == "E_MISSILE_U":
                enemies.append(MissileEnemy(x, y, dir="U", speed=2.0 * mult))
            elif k == "E_MISSILE_D":
                # ステージ5専用ギミック：
                # TM2エディタ座標(214,144)に置いた下方向ミサイルだけ、
                # プレイヤーがTM2エディタ座標(214,156)へ来た時点で起動する。
                trigger_cells = None
                if int(stage) == 5:
                    sy = tilemap_v8_row(stage)
                    if tx == 214 // 2 and ty == (144 - sy) // 2:
                        trigger_cells = [(214, 156)]
                enemies.append(MissileEnemy(x, y, dir="D", speed=2.0 * mult, trigger_tm2_cells=trigger_cells))

            # 配置座標を得点識別子にする。リトライ時に敵は通常どおり再生成されるが、得点だけ重複しない。
            if enemies:
                spawned = enemies[-1]
                spawned.score_key = (int(stage), "enemy", int(tx), int(ty), str(k))
                spawned.score_hp = int(getattr(spawned, "max_hp", getattr(spawned, "hp", 1)) or 1)
                if int(stage) == 9:
                    # Stage9は通常ステージ8個分を縦に連結している。
                    # 通常エネミーは配置された元ステージ相当の256px区画に
                    # プレイヤーが入るまで、出現・更新・当たり判定を停止する。
                    spawned.stage9_section = int((ty * TILE) // SCREEN_H)
                    if isinstance(spawned, MissileEnemy):
                        _apply_stage9_original_missile_trigger(spawned, tx, ty)


    return enemies


def _apply_stage9_original_missile_trigger(missile, tx, ty):
    """Stage9内の各256px区画へ、元Stage1～8のミサイル座標条件を移植する。"""
    if not isinstance(missile, MissileEnemy):
        return

    section = int((ty * TILE) // SCREEN_H)
    source_stage = max(1, min(8, section + 1))
    local_ty = int(ty) - section * (SCREEN_H // TILE)
    editor_x = int(tx) * 2
    editor_y = tilemap_v8_row(source_stage) + local_ty * 2

    missile.trigger_source_stage = source_stage
    missile.trigger_stage9_section = section

    # 通常ステージ側で特定座標条件が設定されているミサイルだけを再現する。
    if missile.dir == "R":
        if editor_x == 138 and editor_y == 206:
            missile.trigger_tm2_x = 138
            missile.trigger_tm2_y_lt = None
        elif editor_x == 168 and editor_y in {192, 194, 196, 198, 200, 202, 204, 206}:
            missile.trigger_tm2_x = 176
            missile.trigger_tm2_y_lt = 208
        elif source_stage == 5:
            if editor_x == 148 and editor_y == 144:
                missile.trigger_tm2_cells = {(158, 142), (158, 144), (158, 146)}
            elif editor_x == 104 and editor_y == 144:
                missile.trigger_tm2_cells = {(112, 146)}
            elif editor_x == 14 and editor_y == 130:
                missile.trigger_tm2_cells = {(22, 130), (22, 132)}
            elif editor_x == 112 and editor_y == 154:
                missile.trigger_tm2_cells = {(120, 150), (120, 152), (120, 154), (120, 156)}
    elif missile.dir == "D" and source_stage == 5:
        if editor_x == 214 and editor_y == 144:
            missile.trigger_tm2_cells = {(214, 156)}


def stage9_field_actor_active(game, actor):
    """Stage9フィールド配置Actorの遅延起動判定。

    現在はStage4中ボスだけが対象。プレイヤーが同じ256px区画に入り、
    Actor自身が現在のカメラ矩形に入った瞬間に一度だけ有効化する。
    有効化後は画面外へ出ても通常どおり行動を継続する。
    """
    if int(getattr(game, "stage", 0)) != 9:
        return True
    if not bool(getattr(actor, "stage9_wait_for_visible_activation", False)):
        return True
    if bool(getattr(actor, "stage9_visible_activated", False)):
        return True

    player = getattr(game, "player", None)
    if player is None:
        return False
    actor_section = int(getattr(actor, "stage9_section", -1))
    player_center_y = float(getattr(player, "y", 0.0)) + float(getattr(player, "h", 16)) * 0.5
    player_section = int(max(0.0, player_center_y) // float(SCREEN_H))
    if actor_section != player_section:
        return False

    cam_x = float(getattr(game, "cam_x", 0.0))
    cam_y = float(getattr(game, "cam_y", 0.0))
    ax = float(getattr(actor, "x", 0.0))
    ay = float(getattr(actor, "y", 0.0))
    aw = float(getattr(actor, "w", 32))
    ah = float(getattr(actor, "h", 32))
    visible = (ax + aw > cam_x and ax < cam_x + SCREEN_W
               and ay + ah > cam_y and ay < cam_y + SCREEN_H)
    if visible:
        actor.stage9_visible_activated = True
        return True
    return False


def normal_stage4_midboss_active(game):
    """通常Stage4中ボスをTM2のX=224通過後に一度だけ有効化する。

    TM2エディタ座標は8pxセル基準。Stage9の歴代Stage4中ボスには適用しない。
    """
    if int(getattr(game, "stage", 0)) != 4:
        return True

    midboss = getattr(game, "midboss", None)
    if midboss is None:
        return False
    trigger_x = getattr(midboss, "stage4_wait_for_tm2_x", None)
    if trigger_x is None:
        return True
    if bool(getattr(midboss, "stage4_tm2_x_activated", False)):
        return True

    player = getattr(game, "player", None)
    if player is None:
        return False

    # 「X軸(224)を超えたら」なので、プレイヤー左端のTM2座標が224より大きくなった時に起動。
    player_tm2_x = int(float(getattr(player, "x", 0.0)) // 8)
    if player_tm2_x > int(trigger_x):
        midboss.stage4_tm2_x_activated = True
        return True
    return False


def stage9_normal_enemy_section_active(game, enemy):
    """Stage9通常エネミーを、配置された256px縦区画内だけで動作させる。

    歴代ボス／歴代中ボス／Stage9専用中ボスは self.enemies に入らないため対象外。
    Stage4ボス召喚フライヤーには召喚元ボスの区画番号を付ける。
    """
    if int(getattr(game, "stage", 0)) != 9:
        return True
    section = getattr(enemy, "stage9_section", None)
    if section is None:
        return True
    player = getattr(game, "player", None)
    if player is None:
        return False
    player_center_y = float(getattr(player, "y", 0.0)) + float(getattr(player, "h", 16)) * 0.5
    player_section = int(max(0.0, player_center_y) // float(SCREEN_H))
    return int(section) == player_section


def draw_platform_span(x, y, w, h, kind, tile=TILE):
    """横or縦に16pxタイルを並べて描画。色12(背景)は透過。"""
    u, v = PLATFORM_UV.get(kind, (80, 0))
    if w >= h:  # 横長（通常の床）
        n = max(1, w // tile)
        for i in range(n):
            pyxel.blt(x + i * tile, y, 0, u, v, tile, tile, 0)
    else:       # 縦長（縦床）
        n = max(1, h // tile)
        for i in range(n):
            pyxel.blt(x, y + i * tile, 0, u, v, tile, tile, 0)

# --- ここからキャラスプライト用設定 ------------------------

# ※ここの(U, V)は「sekka.pyxres」で実際に置いている座標に合わせて直してね
CHAR_UV = {
    "PLAYER" : [
        (0, 144),
        (16,144),
        (32,144),
        (48,144),
      ],  # プレイヤー

    "PLAYER_BIG": [
        (0, 192),   # 0: 立ち
        (32, 192),  # 1: 歩き（右足）
        (32, 160),  # 2: 歩き（左足）
        (0, 224),   # 3: ジャンプ
    ],  # パワーアップ時(32x32)

    "PLAYER_A": [
        (0, 144),
     ],# アーマーありプレイヤー（使わなければそのままでもOK）

    # --- ここから「アーマー」用（※後で pyxel エディタ側の座標に直す） ---
    # アーマー×1（32x32想定）：(u, v) を後で差し替える
    "PLAYER_ARMOR1": [
        (64, 160),   # 0: 立ち
        (64, 192),   # 1: 歩き（右足）
        (32, 224),   # 2: 歩き（左足）
        (64, 224),   # 3: ジャンプ
    ],
    # アーマー×2（32x32想定）：(u, v) を後で差し替える
    "PLAYER_ARMOR2": [
        (96, 160),   # 0: 立ち
        (96, 192),   # 1: 歩き（右足）
        (96, 224),   # 2: 歩き（左足）
        (128, 160),   # 3: ジャンプ
    ],
    # --- ここまでアーマー用 ---


    "WALKER" : [
        (16, 64),
        (32,64),
    ],
    # --- Walker派生用（仮UV：エディタ作成中） ---
    "STOMP_WALKER" : [(64, 64), (80, 64)],     # 踏むとダメージ敵
    "IMMUNE_WALKER" : [(64, 80), (80, 80)],    # ショット無効敵

    # --- New enemies ---
    "WARP_ENEMY" : [(0, 64)],
    "CHASER_WALKER" : [(32, 112), (48, 112), (0, 96), (48, 64), (16, 112)],
    "SPLIT_FLYER" : [(16, 96)],
    "AIM_SHOOTER" : [(32, 96)],
    
    "HOPPER" :[
        (16, 80),
        (32,80),
        (48,80),
    ],

    "FLYER"  : [(48, 96),
    ],

    "SHOOTER": [(0, 112),
    ],

    "BOSS"   :[ (0, 64),
    ],

    # --- Boss/Midboss placeholders (stage-unique keys; can point to same UV for now) ---
    # --- Boss/Midboss sprites ---
    # Stage1-4 midboss: sekka.pyxres Image1 / midboss size
    "MID1"  : [(128, 0), (160, 0)],
    "MID2"  : [(128, 32), (160, 32), (192, 0)],
    "MID3"  : [(224, 0)],
    "MID4"  : [(192, 32), (224, 32)],

    # Stage5-9 midboss: sekka.pyxres Image0 / midboss size
    # MID8/MID9: walk=巡回2枚 / stop=停止1枚 / jump=ジャンプ1枚
    "MID5"  : [(224, 224), (192, 224)],
    "MID6"  : [(224, 192), (192, 192)],
    "MID7"  : [(224, 160), (192, 160)],
    "MID8"  : [(224, 128), (192, 128), (224, 96), (192, 96)],
    "MID9"  : [(192, 16), (224, 16), (224, 64), (160, 160)],

    # Stage1-4 boss: sekka.pyxres Image1 / boss size
    "BOSS1" : [(0, 0), (64, 0)],
    "BOSS2" : [(0, 64), (64, 64), (128, 64), (192, 64)],
    "BOSS3" : [(0, 128), (64, 128), (128, 128), (192, 128)],
    "BOSS4" : [(0, 192), (64, 192), (128, 192)],

    # Stage5-8 boss: sekka.pyxres Image2 / boss size
    "BOSS5" : [(0, 0), (64, 0), (128, 0), (192, 0)],
    "BOSS6" : [(0, 64), (64, 64), (128, 64), (192, 64)],
    "BOSS7" : [(0, 128), (64, 128)],
    "BOSS8" : [(0, 192), (64, 192), (128, 192), (192, 192), (192, 128)],

    # Stage9 final boss: sekka3.pyxres Image1 / boss size
    "FINAL" : [(0, 0), (64, 0), (128, 0), (192, 0)],
    # -------------------------------------------------------------------------------

    "REAPER" : [(48, 128),
    ],
    # --- Missile sprites (direction x state) ---
    "MISSILE_L": [(80, 96)],      # ( ) 右→左 通常
    "MISSILE_R": [(64, 96)],      # ( ) 左→右 通常
    "MISSILE_D": [(80, 96)],      # ( ) 上→下 通常
    "MISSILE_U": [(80, 96)],      # ( ) 下→上 通常

    "MISSILE_L_EXP": [(64, 112)],  # ( ) 右→左 爆発
    "MISSILE_R_EXP": [(64, 112)],  # ( ) 左→右 爆発
    "MISSILE_D_EXP": [(64, 112)],  # ( ) 上→下 爆発
    "MISSILE_U_EXP": [(64, 112)],  # ( ) 下→上 爆発

}

def draw_char_sprite(name, x, y, w, h, face=1, frame=0, img=0):
    frames = CHAR_UV.get(name, [(0, 16)])
    u, v = frames[frame % len(frames)]

    x = int(x); y = int(y); w = int(w); h = int(h)
    img = int(img)

    if face >= 0:
        pyxel.blt(x, y, img, u, v,  w, h, 0)
    else:
        pyxel.blt(x, y, img, u, v, -w, h, 0)   # ★ x+w をやめる

def draw_normal_bullet(x, y, w, h):
    """通常ショットを円形に近い見た目で描画する。

    Bullet 本体の x/y/w/h（当たり判定）は変更せず、描画中心だけを
    既存の当たり判定矩形の中央に合わせる。プレイヤー弾・敵弾共通。
    """
    x = int(x); y = int(y); w = max(1, int(w)); h = max(1, int(h))
    cx = x + w // 2
    cy = y + h // 2

    # 5x5相当の小さな円。外周を濃色、中心を従来色にして視認性も維持。
    pyxel.circ(cx, cy, 2, 0)
    pyxel.circ(cx, cy, 1, 7)


def draw_energy_bullet(x, y, w, h):
    """ハイパーショット用の丸いエネルギー弾描画。

    当たり判定に使う Bullet の x/y/w/h は変更せず、描画だけを
    角ばった矩形から丸みのある形へ変更する。
    - 6x30 の縦長弾: 上下に丸い先端を持つカプセル形
    - 10x10/16x16 など: 円形に近いエネルギー弾
    """
    x = int(x); y = int(y); w = max(1, int(w)); h = max(1, int(h))
    cx = x + w // 2
    cy = y + h // 2

    # 小さい弾は、当たり判定の外へ大きくはみ出さない範囲で円形にする。
    if abs(w - h) <= 2:
        r = max(2, min(w, h) // 2)
        pyxel.circ(cx, cy, r, 10)
        if r >= 3:
            pyxel.circb(cx, cy, r, 7)
            pyxel.circ(cx, cy, max(1, r - 3), 7)
        return

    # 縦長/横長はカプセル形。矩形＋両端円で丸みを出す。
    if h > w:
        r = max(2, w // 2)
        pyxel.rect(x, y + r, w, max(1, h - r * 2), 10)
        pyxel.circ(cx, y + r, r, 10)
        pyxel.circ(cx, y + h - r - 1, r, 10)
        pyxel.line(cx, y + r + 1, cx, y + h - r - 2, 7)
        pyxel.pset(cx, y + r, 7)
        pyxel.pset(cx, y + h - r - 1, 7)
    else:
        r = max(2, h // 2)
        pyxel.rect(x + r, y, max(1, w - r * 2), h, 10)
        pyxel.circ(x + r, cy, r, 10)
        pyxel.circ(x + w - r - 1, cy, r, 10)
        pyxel.line(x + r + 1, cy, x + w - r - 2, cy, 7)
        pyxel.pset(x + r, cy, 7)
        pyxel.pset(x + w - r - 1, cy, 7)

# === ANCHOR END ===
class Conveyor:
    """静止。上に乗ったものを水平方向に流すだけ。"""
    def __init__(self, x, y, w, dir_right=True, spd=1.0):
        self.x, self.y, self.w = x, y, max(TILE, w)
        self.h = TILE
        self.dir_right = bool(dir_right)
        self.spd = abs(spd)
        self.dx_last = 0     # 互換用(未使用)
        self.dy_last = 0

    def update(self):
        pass  # 自身は動かない

    def draw(self):
        draw_platform_span(self.x, self.y, self.w, TILE, "AUTO")
# === ANCHOR END ===

class Bullet:
    def __init__(self, x, y, vx, power, vy=0):
        self.x = x; self.y = y; self.vx = vx; self.vy = vy
        self.w = 6; self.h = 3  # ほんの少しだけ拡大
        self.power = power
        self.alive = True
        self.max_range = 240
        self._start_x = x

    def trigger_missile_explosion(self):
        """既存ミサイル用の爆発エフェクトを流用する。
        Stage3ボスショット専用タグで呼ばれる想定。
        """
        if getattr(self, "explode_timer", 0) > 0:
            return
        self.explode_timer = int(getattr(self, "explode_frames", 30))
        self.vx = 0
        self.vy = 0
        # 既存ミサイル爆発スプライト(16x16)と同じ見た目に寄せる。
        # 弾の中心を保ったまま当たり判定も16x16にする。
        cx = self.x + self.w * 0.5
        cy = self.y + self.h * 0.5
        self.w = 16
        self.h = 16
        self.x = cx - self.w * 0.5
        self.y = cy - self.h * 0.5
        self.max_range = 9999
        self.alive = True
        play_sfx_at("EXPLOSION", self.x, self.y, self.w, self.h, margin=16)

    def update(self, world_h=None):
        if getattr(self, "explode_timer", 0) > 0:
            self.explode_timer -= 1
            if self.explode_timer <= 0:
                self.alive = False
            return

        self.x += self.vx
        self.y += self.vy

        # ---- lifetime ----
        # 既存: X方向の射程で消える（横スクロール前提）
        if abs(self.x - self._start_x) > self.max_range:
            self.alive = False

        # FIX: Stage9 は縦長フィールドなので、固定 FLOOR_Y(208) 基準で
        # Y寿命を切ると、下段で撃った瞬間にプレイヤー弾/敵弾が消えてしまう。
        # 呼び出し側から渡された現在ステージ全体の高さを基準にする。
        if world_h is None:
            world_h = int(globals().get("CURRENT_STAGE_WORLD_H", WORLD_H))
        if self.y < -32 or self.y > int(world_h) + 64:
            self.alive = False

        if self.x < -16 or self.x > WORLD_W + 16:
            self.alive = False

    def draw(self):
        if getattr(self, "explode_timer", 0) > 0:
            # エネミー「ミサイル」と同じ爆発絵を流用する。
            draw_char_sprite("MISSILE_D_EXP", self.x, self.y, 16, 16, face=1, frame=0)
            return

        # ハイパーショット(power=2 / kind="power")は、
        # 当たり判定(self.x, self.y, self.w, self.h)を一切変えず、
        # 描画だけ丸みのあるエネルギー弾にする。
        if getattr(self, "kind", "normal") == "power" or int(getattr(self, "power", 1)) >= 2:
            # プレイヤー／エネミー双方のチャージショットへ、
            # 全場面で上下左右1pxの黒い輪郭影を付ける。
            # 弾の実座標・サイズ・当たり判定には触れない。
            if True:
                try:
                    for col in range(1, 16):
                        pyxel.pal(col, 0)
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        draw_energy_bullet(self.x + dx, self.y + dy, self.w, self.h)
                finally:
                    pyxel.pal()

            draw_energy_bullet(self.x, self.y, self.w, self.h)
            return

        draw_normal_bullet(self.x, self.y, self.w, self.h)
# === ANCHOR END ===

# ===== 敵種(3種+ボス+死神) =====
# === ANCHOR: ENEMIES (DO NOT EDIT) ===
class EnemyBase:
    def __init__(self, x, y, w=16, h=16, vx=1):
        self.x=x; self.y=y; self.w=w; self.h=h; self.vx=vx
        self.vy = 0
        self.alive = True

    def update(self): pass
    def damage(self, dmg): self.alive = False
    def draw(self, name="ENEMY", frame=0, img=0):
        face = getattr(self, "face", 1 if self.vx >= 0 else -1)
        # 通常エネミーは全場面でプレイヤーと同じ1px黒輪郭を付ける。
        # ボス／中ボスは専用描画側で輪郭を付けるため、ここでは二重描画を避ける。
        is_boss_actor = bool(getattr(self, "sprite_key", None))
        if not is_boss_actor:
            try:
                for col in range(1, 16):
                    pyxel.pal(col, 0)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    draw_char_sprite(name, self.x + dx, self.y + dy, self.w, self.h, face, frame, img=img)
            finally:
                pyxel.pal()

        # ステージ9の通常エネミーだけ、歴代ボス／歴代中ボスと同じ反転パレットで描画する。
        # ボス／中ボスは Boss.draw() 側で個別管理するため、ここでは通常エネミーだけが対象。
        game = getattr(Game, "_instance", None) if "Game" in globals() else None
        stage9_normal_enemy = (
            not is_boss_actor
            and game is not None
            and int(getattr(game, "stage", 1)) == 9
        )
        if stage9_normal_enemy:
            try:
                # 0番色は透明色のため維持。既存のステージ9歴代ボスと同じ反転規則。
                for col in range(1, 16):
                    pyxel.pal(col, 16 - col)
                draw_char_sprite(name, self.x, self.y, self.w, self.h, face, frame, img=img)
            finally:
                pyxel.pal()
        else:
            draw_char_sprite(name, self.x, self.y, self.w, self.h, face, frame, img=img)

def normal_enemy_gravity_move_mult():
    """通常エネミー用。重力異常中だけ横移動量を補正する。"""
    game = Game._instance
    if game:
        env = getattr(game, "environment", "NONE")
        if env == "GRAVITY_ANOMALY":
            return GRAVITY_ANOMALY_MOVE_MULT
        if env == "HIGH_GRAVITY":
            return HIGH_GRAVITY_MOVE_MULT
    return 1.0

class Walker(EnemyBase):
    def __init__(self, x, y, left, right, spd=1):
        super().__init__(x, y, 16, 16, spd)
        self.left=left; self.right=right
        self.turn_cd = 0

    def update(self, level=None, TILES_X=None, TILES_Y=None):
        if self.turn_cd > 0:
            self.turn_cd -= 1
        self.x += self.vx * normal_enemy_gravity_move_mult()
        if self.x <= self.left or self.x >= self.right - self.w:
            self.x = clamp(self.x, self.left, self.right - self.w)
            self.vx *= -1
            self.turn_cd = 8
            return
        if level is not None and self.turn_cd == 0:
            front_x = self.x + (self.w if self.vx > 0 else -1)
            foot_y  = self.y + self.h + 1
            tx = int(front_x // TILE)
            ty = int(foot_y  // TILE)
            if not tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx, ty):
                self.vx *= -1
                self.turn_cd = 8

    def draw(self):
        # 2コマ歩きアニメ
        frame = (pyxel.frame_count // 8) % 2  # CHAR_UV["WALKER"] が2枚ならOK
        super().draw("WALKER", frame)

class StompDamageWalker(Walker):
    def draw(self):
        # Walkerと同じ2コマ歩きアニメ
        frame = (pyxel.frame_count // 8) % 2
        # EnemyBase.draw を直接呼ぶ（WALKERではなく専用キー）
        EnemyBase.draw(self, "STOMP_WALKER", frame)


class NormalShotImmuneWalker(Walker):
    def draw(self):
        # Walkerと同じ2コマ歩きアニメ
        frame = (pyxel.frame_count // 8) % 2
        EnemyBase.draw(self, "IMMUNE_WALKER", frame)

class MissileEnemy(EnemyBase):
    """ミサイル系：プレイヤーが近づいたら生成（発射）され、直線移動する。"""
    def __init__(self, x, y, dir="L", speed=2.0, proximity=8, explode_frames=30,
                 activate_x_range=MISSILE_ACTIVATE_X_RANGE,
                 activate_y_range=MISSILE_ACTIVATE_Y_RANGE,
                 trigger_tm2_cells=None,
                 trigger_tm2_x=None,
                 trigger_tm2_y_lt=None):
        vx = vy = 0
        if dir == "L":
            vx = -speed
        elif dir == "R":
            vx = speed
        elif dir == "U":
            vy = -speed
        elif dir == "D":
            vy = speed

        super().__init__(x, y, 16, 16, vx)
        self.vy = vy
        self.dir = dir
        self.proximity = proximity
        self.explode_timer = 0
        self.explode_frames = explode_frames

        # ステージ開始時点では「未生成」扱い。
        # 近づいた瞬間に、エディタで置いた座標から発射する。
        self.spawn_x = x
        self.spawn_y = y
        self.active = False
        self.activate_x_range = activate_x_range
        self.activate_y_range = activate_y_range

        # 特定ギミック用：
        # 指定した「Pyxelエディタ上のTM2座標(8px単位)」へ
        # プレイヤーの左足元セルが来たら起動。
        #
        # 重要：
        # ここに入れる座標は、ステージ縦積みを含む「エディタ表示そのまま」の座標。
        # 例：ステージ5の中間フラグなら (112,146) のまま入れる。
        # None の場合は従来どおり、ミサイルの近くに来たら起動する。
        self.trigger_tm2_cells = set(trigger_tm2_cells or [])

        # 特定ギミック用：
        # 指定した「Pyxelエディタ上のTM2 X座標(8px単位)」へ
        # プレイヤーの当たり判定全体が到達したら起動する。
        # Y座標は見ず、X軸だけで判定する。
        self.trigger_tm2_x = trigger_tm2_x

        # trigger_tm2_x と併用する任意条件。
        # プレイヤーの当たり判定が、指定したTM2エディタY座標より上方にある時だけ起動する。
        self.trigger_tm2_y_lt = trigger_tm2_y_lt

        # Stage9では、縦に並べた各256px区画を元のStage1～8として扱う。
        # 特定座標トリガーを元ステージのTM2座標系で評価するために使用する。
        self.trigger_source_stage = None
        self.trigger_stage9_section = None

        # 発射口の壁・床に半分埋めて配置しても、生成直後に自分の設置タイルを
        # 衝突扱いして即爆発しないようにする。設置時に重なっていたセルだけ、
        # ミサイルがそこから完全に抜けるまで衝突判定を無視する。
        self._spawn_overlap_cells = None

    def _should_activate(self, player):
        if player is None:
            return True

        # trigger_tm2_x があるミサイルは、距離判定ではなく指定X軸到達で起動する。
        if self.trigger_tm2_x is not None:
            left = int(player.x // 8)
            right = int((player.x + player.w - 1) // 8)
            if not (left <= int(self.trigger_tm2_x) <= right):
                return False

            if self.trigger_tm2_y_lt is not None:
                g = Game._instance
                stage = getattr(g, "stage", 1) if g is not None else 1
                source_stage = getattr(self, "trigger_source_stage", None)
                section = getattr(self, "trigger_stage9_section", None)
                if int(stage) == 9 and source_stage is not None and section is not None:
                    sy = tilemap_v8_row(int(source_stage))
                    local_y = player.y - int(section) * SCREEN_H
                    top = int(local_y // 8) + sy
                    bottom = int((local_y + player.h - 1) // 8) + sy
                else:
                    sy = tilemap_v8_row(stage)
                    top = int(player.y // 8) + sy
                    bottom = int((player.y + player.h - 1) // 8) + sy
                return top < int(self.trigger_tm2_y_lt) and bottom < int(self.trigger_tm2_y_lt)

            return True

        # trigger_tm2_cells があるミサイルは、距離判定ではなく指定座標判定で起動する。
        if self.trigger_tm2_cells:
            # プレイヤーの当たり判定「全体」が、指定されたTM2エディタ8pxセルに触れたら起動する。
            # ここでは足元1点だけにはしない。
            #
            # trigger_tm2_cells は「エディタ表示そのまま」の8px座標で保持しているため、
            # プレイヤーのローカルYセルにステージ縦積み分 sy を足して比較する。
            g = Game._instance
            stage = getattr(g, "stage", 1) if g is not None else 1
            source_stage = getattr(self, "trigger_source_stage", None)
            section = getattr(self, "trigger_stage9_section", None)

            left = int(player.x // 8)
            right = int((player.x + player.w - 1) // 8)
            if int(stage) == 9 and source_stage is not None and section is not None:
                sy = tilemap_v8_row(int(source_stage))
                local_y = player.y - int(section) * SCREEN_H
                top = int(local_y // 8) + sy
                bottom = int((local_y + player.h - 1) // 8) + sy
            else:
                sy = tilemap_v8_row(stage)
                top = int(player.y // 8) + sy
                bottom = int((player.y + player.h - 1) // 8) + sy

            for ty in range(top, bottom + 1):
                for tx in range(left, right + 1):
                    if (tx, ty) in self.trigger_tm2_cells:
                        return True
            return False

        pcx = player.x + player.w / 2
        pcy = player.y + player.h / 2
        mcx = self.spawn_x + self.w / 2
        mcy = self.spawn_y + self.h / 2
        return (abs(pcx - mcx) <= self.activate_x_range and
                abs(pcy - mcy) <= self.activate_y_range)

    def _activate(self):
        self.x = self.spawn_x
        self.y = self.spawn_y
        self.active = True
        play_sfx_at("SHOT", self.x, self.y, self.w, self.h)

    def _trigger_explode(self):
        if self.explode_timer <= 0:
            self.explode_timer = self.explode_frames
            self.active = True
            play_sfx_at("EXPLOSION", self.x, self.y, self.w, self.h, margin=16)

    def update(self, level=None, TILES_X=None, TILES_Y=None, player=None):
        if not self.alive:
            return

        # まだプレイヤーが近づいていない間は、描画も移動も判定もしない。
        if not self.active:
            if self._should_activate(player):
                self._activate()
            else:
                return

        if self.explode_timer > 0:
            self.explode_timer -= 1
            if self.explode_timer <= 0:
                self.alive = False
            return

        # --- move (with tile collision) ---
        nx = self.x + self.vx
        ny = self.y + self.vy

        # ブロック等に接触 -> 爆発（ブロック破壊なし）
        if level is not None and TILES_X is not None and TILES_Y is not None:
            l = int(nx // TILE)
            r = int((nx + self.w - 1) // TILE)
            t = int(ny // TILE)
            b = int((ny + self.h - 1) // TILE)
            # 初回だけ、設置位置で重なっている地形セルを記録する。
            if self._spawn_overlap_cells is None:
                sl = int(self.spawn_x // TILE)
                sr = int((self.spawn_x + self.w - 1) // TILE)
                st = int(self.spawn_y // TILE)
                sb = int((self.spawn_y + self.h - 1) // TILE)
                self._spawn_overlap_cells = {
                    (sx, sy) for sy in range(st, sb + 1) for sx in range(sl, sr + 1)
                    if is_solid_for_player(tile_at(level, TILES_X, TILES_Y, sx, sy))
                }

            current_cells = {(tx, ty) for ty in range(t, b + 1) for tx in range(l, r + 1)}
            still_in_launcher = bool(current_cells & self._spawn_overlap_cells)
            if not still_in_launcher:
                self._spawn_overlap_cells.clear()

            hit_solid = False
            for ty in range(t, b + 1):
                for tx in range(l, r + 1):
                    # 発射口として使っている設置セルだけは、抜け切るまで無視。
                    if (tx, ty) in self._spawn_overlap_cells:
                        continue
                    tt = tile_at(level, TILES_X, TILES_Y, tx, ty)
                    if is_solid_for_player(tt):
                        hit_solid = True
                        break
                if hit_solid:
                    break
            if hit_solid:
                self._trigger_explode()
                return

        # no tile hit -> apply move
        self.x = nx
        self.y = ny

        # --- screen edge -> explode ---
        # Stage9ではY座標がワールド座標になるため、固定 0..SCREEN_H を使うと
        # 下層に置いたミサイルが発射直後に画面外扱いされて即爆発する。
        # 現在のカメラ表示範囲を基準に判定する。
        margin = 64
        g = Game._instance
        cam_x = float(getattr(g, "cam_x", 0.0)) if g is not None else 0.0
        cam_y = float(getattr(g, "cam_y", 0.0)) if g is not None else 0.0
        left_bound = cam_x - margin
        right_bound = cam_x + SCREEN_W + margin
        top_bound = cam_y - margin
        bottom_bound = cam_y + SCREEN_H + margin
        if (self.x + self.w < left_bound or self.x > right_bound or
                self.y + self.h < top_bound or self.y > bottom_bound):
            self._trigger_explode()
            return

        # --- proximity contact -> explode ---
        if player is not None:
            px, py, pw, ph = player.x, player.y, player.w, player.h
            if aabb(self.x - self.proximity, self.y - self.proximity,
                    self.w + self.proximity * 2, self.h + self.proximity * 2,
                    px, py, pw, ph):
                self._trigger_explode()

    def damage(self, dmg):

        # 撃たれたら爆発して消える
        self._trigger_explode()

    def draw(self):
        if not self.active:
            return
        # direction key is fixed by editor marker
        d = self.dir
        if self.explode_timer > 0:
            name = f"MISSILE_{d}_EXP"
        else:
            name = f"MISSILE_{d}"
        # Stage9に配置されたミサイルだけ、通常版と区別できるよう描画色を反転する。
        g = Game._instance
        if g is not None and int(getattr(g, "stage", 0)) == 9:
            try:
                for c in range(1, 16):
                    pyxel.pal(c, 16 - c)
                draw_char_sprite(name, self.x, self.y, self.w, self.h, face=1, frame=0)
            finally:
                pyxel.pal()
        else:
            draw_char_sprite(name, self.x, self.y, self.w, self.h, face=1, frame=0)


class Hopper(EnemyBase):
    def __init__(self, x, y, left, right, spd=0.3):
        super().__init__(x, y, 16, 16, spd)
        self.left = left
        self.right = right
        self.vy = 0
        self.g = 0.3
        self.jump_cd = 0
        self.on_ground = False

    def update(self, level=None, TILES_X=None, TILES_Y=None):
        # ---- jump trigger (only when on ground) ----
        if self.on_ground and self.jump_cd <= 0:
            game = Game._instance
            env = getattr(game, "environment", "NONE") if game else "NONE"
            if env == "GRAVITY_ANOMALY":
                self.vy = -4.0 * JUMP_VY_MULT * GRAVITY_ANOMALY_JUMP_MULT
            elif env == "HIGH_GRAVITY":
                self.vy = -4.0 * JUMP_VY_MULT * HIGH_GRAVITY_JUMP_MULT
            else:
                self.vy = -4.0 * JUMP_VY_MULT
            play_sfx_at("ENEMY_JUMP", self.x, self.y, self.w, self.h)
            self.jump_cd = 60
            self.on_ground = False
        elif self.jump_cd > 0:
            self.jump_cd -= 1

        # ---- gravity ----
        game = Game._instance
        env = getattr(game, "environment", "NONE") if game else "NONE"
        gravity_anomaly = (env == "GRAVITY_ANOMALY")
        high_gravity = (env == "HIGH_GRAVITY")
        if gravity_anomaly:
            self.vy += self.g * GRAVITY_ANOMALY_GRAVITY_MULT
        elif high_gravity:
            self.vy += self.g * HIGH_GRAVITY_GRAVITY_MULT
        else:
            self.vy += self.g
        self.y += self.vy

        # ---- horizontal (faster in air) ----
        air_mult = HOPPER_AIR_X_MULT if abs(self.vy) > 0.01 else 1.0
        if gravity_anomaly:
            self.x += self.vx * air_mult * GRAVITY_ANOMALY_MOVE_MULT
        elif high_gravity:
            self.x += self.vx * air_mult * HIGH_GRAVITY_MOVE_MULT
        else:
            self.x += self.vx * air_mult

        # ---- patrol range ----
        if self.x < self.left or self.x > self.right - self.w:
            self.x = clamp(self.x, self.left, self.right - self.w)
            self.vx *= -1

        # ---- ground collision ----
        self.on_ground = False
        if level is not None and TILES_X is not None and TILES_Y is not None:
            # 足元のタイルを確認して、落下中に床に乗ったら着地
            foot_y = self.y + self.h
            ty = int(foot_y // TILE)
            # 16幅の左右2点を見る（段差・角での抜け防止）
            tx_l = int((self.x + 2) // TILE)
            tx_r = int((self.x + self.w - 3) // TILE)

            if self.vy >= 0:
                hit = False
                for tx in (tx_l, tx_r):
                    if tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx, ty):
                        hit = True
                        break
                if hit:
                    ground_top = ty * TILE
                    if self.y + self.h >= ground_top:
                        self.y = ground_top - self.h
                        self.vy = 0
                        self.on_ground = True
        else:
            # フォールバック：従来の固定床（どうしても level が渡ってこない場合）
            if self.y > FLOOR_Y - self.h:
                self.y = FLOOR_Y - self.h
                self.vy = 0
                self.on_ground = True

    def draw(self):
        if self.on_ground:
            frame = (pyxel.frame_count // 8) % 2  # 歩き2コマ
        else:
            frame = 2  # ジャンプ
        super().draw("HOPPER", frame)

class Flyer(EnemyBase):

    def __init__(self, x, y, left, right, spd=1, active=True,
                 activate_x_range=FLYER_ACTIVATE_X_RANGE,
                 activate_y_range=FLYER_ACTIVATE_Y_RANGE,
                 top=None, bottom=None):
        super().__init__(x, y, 16, 16, spd)
        self.left = left
        self.right = right

        # MARK_A/MARK_U の両方がある時だけ上下往復。
        # 範囲指定なしは、元の基本動作「ゆっくり下にジグザグ降下」を使う。
        self.has_vertical_range = (top is not None and bottom is not None)
        if self.has_vertical_range:
            self.top = top
            self.bottom = bottom
            if self.bottom < self.top:
                self.top, self.bottom = self.bottom, self.top
            self.vy = max(0.4, abs(spd) * 0.6)
        else:
            self.top = None
            self.bottom = None
            self.vy = 0.35

        # エディタ配置の場合は active=False で生成し、
        # プレイヤーが近づいたら、配置座標から行動開始する。
        self.spawn_x = x
        self.spawn_y = y
        self.active = active
        self.activate_x_range = activate_x_range
        self.activate_y_range = activate_y_range

    def _should_activate(self, player):
        if player is None:
            return True
        pcx = player.x + player.w / 2
        pcy = player.y + player.h / 2
        fcx = self.spawn_x + self.w / 2
        fcy = self.spawn_y + self.h / 2
        return (abs(pcx - fcx) <= self.activate_x_range and
                abs(pcy - fcy) <= self.activate_y_range)

    def _activate(self):
        self.x = self.spawn_x
        self.y = self.spawn_y
        self.active = True

    def update(self, player=None):
        if not self.alive:
            return

        # まだプレイヤーが近づいていない間は、描画も移動も判定もしない。
        if not self.active:
            if self._should_activate(player):
                self._activate()
            else:
                return

        if self.has_vertical_range:
            # 範囲指定あり：指定した上下範囲内だけを往復。
            self.x += self.vx
            self.y += self.vy

            if self.x < self.left:
                self.x = self.left
                self.vx = abs(self.vx)
            elif self.x > self.right - self.w:
                self.x = self.right - self.w
                self.vx = -abs(self.vx)

            if self.y < self.top:
                self.y = self.top
                self.vy = abs(self.vy)
            elif self.y > self.bottom - self.h:
                self.y = self.bottom - self.h
                self.vy = -abs(self.vy)

            self.y += pyxel.sin(pyxel.frame_count * 0.1) * 0.5
            self.y = clamp(self.y, self.top, self.bottom - self.h)
        else:
            # 範囲指定なし：元の基本動作。
            # ゆっくり下へ降りながら、左右にジグザグ移動する。
            self.x += self.vx
            self.y += self.vy

            if self.x < self.left:
                self.x = self.left
                self.vx = abs(self.vx)
            elif self.x > self.right - self.w:
                self.x = self.right - self.w
                self.vx = -abs(self.vx)

            # 画面下へ抜けたら敵として消す。上昇や狭い上下往復はさせない。
            if self.y > WORLD_H + self.h:
                self.alive = False

    def draw(self):
        if not self.active:
            return
        super().draw("FLYER")

class Shooter(EnemyBase):
    """その場で左右を向き、プレイヤー方向へランダムに射撃する固定砲台"""
    def __init__(self, x, y):
        super().__init__(x, y, 16, 16, 0)
        self.face = 1
        self.shoot_cd = random.randint(45, 120)  # 0.75〜2秒程度

    def update(self, px=None, py=None, shoot_cb=None):
        # 向き更新(Xのみ)
        if px is not None:
            self.face = 1 if px >= self.x else -1

        # 射撃クールダウン
        if self.shoot_cd > 0:
            self.shoot_cd -= 1
        else:
            # 発射:プレイヤー方向へ水平弾
            if shoot_cb is not None:
                vx = 3 * self.face
                bx = self.x + (self.w if self.face > 0 else -8)
                by = self.y + self.h // 2
                shoot_cb(bx, by, vx)
            self.shoot_cd = random.randint(45, 120)

    def draw(self):
        # 本体はスプライト、口だけ四角で上書き（演出用）
        super().draw("SHOOTER")
        mx = self.x + (self.w - 3 if self.face > 0 else -1)
        my = self.y + self.h // 2 - 1
        pyxel.rect(mx, my, 3, 3, 0)

class WarpEnemy(EnemyBase):
    """一定時間ごとに、プレイヤー進行方向の直前へワープする反射敵。"""
    def __init__(self, x, y, hp=2, interval=150, warn_frames=30):
        super().__init__(x, y, 16, 16, 0)
        self.hp = hp
        self.face = 1
        self.interval = int(interval)
        self.warn_frames = int(warn_frames)
        self.timer = 0

    def _same_screen_as_player(self, player):
        if player is None:
            return False
        return int((self.x + self.w / 2) // SCREEN_W) == int((player.x + player.w / 2) // SCREEN_W)

    def _can_warp_to(self, x, y, level, TILES_X, TILES_Y):
        if level is None or TILES_X is None or TILES_Y is None:
            return True
        # 本体がブロックへ重なる位置は不可。
        l, r, t, b = rect_to_tiles(x, y, self.w, self.h)
        for ty in range(t, b + 1):
            for tx in range(l, r + 1):
                if is_solid_for_player(tile_at(level, TILES_X, TILES_Y, tx, ty)):
                    return False
        # 足元が無い＝奈落/空中扱いなので不可。
        foot_ty = int((y + self.h + 1) // TILE)
        tx_l = int((x + 2) // TILE)
        tx_r = int((x + self.w - 3) // TILE)
        return (tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx_l, foot_ty) or
                tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx_r, foot_ty))

    def update(self, level=None, TILES_X=None, TILES_Y=None, player=None):
        if player is None or not self._same_screen_as_player(player):
            # 見えない画面ではカウント停止。
            return
        self.face = 1 if player.x >= self.x else -1
        self.timer += 1
        if self.timer < self.interval:
            return
        self.timer = 0
        pface = getattr(player, "face", 1)
        target_x = player.x + (player.w + 8) * pface
        target_y = player.y + player.h - self.h
        if self._can_warp_to(target_x, target_y, level, TILES_X, TILES_Y):
            # ワープ実行時に「フォン！」音。移動前後どちらかが画面内なら鳴らす。
            if is_rect_on_screen(self.x, self.y, self.w, self.h, margin=16) or is_rect_on_screen(target_x, target_y, self.w, self.h, margin=16):
                play_sfx("WARP")
            self.x = clamp(target_x, 0, WORLD_W - self.w)
            self.y = target_y
            self.face = -pface

    def damage(self, dmg):
        self.hp -= int(dmg)
        if self.hp <= 0:
            self.alive = False

    def draw(self):
        # ワープ直前0.5秒は点滅。
        if self.timer >= self.interval - self.warn_frames and (pyxel.frame_count // 4) % 2 == 0:
            return
        super().draw("WARP_ENEMY", 0)


class ChaserWalker(EnemyBase):
    """プレイヤーを高速追尾するウォーカー。

    - MARK_L / MARK_R が両方ある場合だけ、その範囲内で追尾する。
    - プレイヤーが指定範囲外、または自分のジャンプで越えられない奈落の直前では停止する。
    - 越えられる奈落や段差は、ホッパー同等ジャンプ力で飛び越える。
    """
    def __init__(self, x, y, spd=2.5, hp=2, left=None, right=None, bounded=False):
        super().__init__(x, y, 16, 16, spd)
        self.hp = hp
        self.base_spd = abs(spd)
        self.left = left
        self.right = right
        self.bounded = bool(bounded)
        self.face = 1
        self.g = 0.3
        self.jump_vy = -4.0 * JUMP_VY_MULT
        self.on_ground = False
        self.slide_timer = 0
        self.prev_dir = 1
        self.stop_blocked = False

    def _hits_solid(self, x, y, level, TILES_X, TILES_Y):
        l, r, t, b = rect_to_tiles(x, y, self.w, self.h)
        for ty in range(t, b + 1):
            for tx in range(l, r + 1):
                if is_solid_for_player(tile_at(level, TILES_X, TILES_Y, tx, ty)):
                    return True
        return False

    def _ground_at_world_x(self, level, TILES_X, TILES_Y, world_x, foot_y=None):
        if foot_y is None:
            foot_y = self.y + self.h + 1
        tx = int(world_x // TILE)
        ty = int(foot_y // TILE)
        return tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx, ty)

    def _player_out_of_bounds(self, player):
        if not self.bounded or player is None:
            return False
        pcx = player.x + player.w / 2
        return pcx < self.left or pcx > self.right

    def _next_x_out_of_bounds(self, nx):
        if not self.bounded:
            return False
        return nx < self.left or nx > self.right - self.w

    def _gap_jump_possible(self, level, TILES_X, TILES_Y, dir):
        """前方が本当の奈落か、ジャンプで越えられる奈落かを判定する。

        旧判定は「足元の真横1点に地面が無い」だけで奈落扱いしていたため、
        1タイルの段差・少し低い足場・上り段差の壁際でも停止しやすかった。
        ここではまず「普通の段差/足場の続き」を除外し、それでも深い穴だけを
        奈落としてジャンプ可否判定に回す。
        """
        foot_y = self.y + self.h + 1
        front_x = self.x + (self.w + 1 if dir > 0 else -2)
        front_tx = int(front_x // TILE)
        foot_ty = int(foot_y // TILE)

        # 同じ高さに地面があるなら奈落ではない。
        if tile_is_ground_for_enemy(level, TILES_X, TILES_Y, front_tx, foot_ty):
            return False, False

        # 目の前に壁/上り段差がある場合は奈落ではない。
        # この後の横衝突処理でジャンプして登らせる。
        body_top_ty = int((self.y + 2) // TILE)
        body_bottom_ty = int((self.y + self.h - 2) // TILE)
        for ty_check in range(body_top_ty, body_bottom_ty + 1):
            if is_solid_for_player(tile_at(level, TILES_X, TILES_Y, front_tx, ty_check)):
                return False, False

        # 1〜2タイル下に地面がある場合は、ただの下り段差/低い足場として扱う。
        # ここを奈落扱いすると、添付画像のような普通の段差で止まってしまう。
        for drop in range(1, 3):
            if tile_is_ground_for_enemy(level, TILES_X, TILES_Y, front_tx, foot_ty + drop):
                return False, False

        # 少し先に同じ高さ/少し下の地面がすぐ見える場合も、通常の段差として扱う。
        # 1タイル程度の切れ目やタイル端のズレを奈落判定しないための保険。
        for step in range(1, 3):
            tx = front_tx + dir * step
            for drop in range(0, 3):
                if tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx, foot_ty + drop):
                    return False, False

        # ここまで来たら「深い穴」とみなし、ホッパー相当ジャンプ中に届く
        # 着地点があるかを調べる。
        air_frames = max(1, int((abs(self.jump_vy) * 2.0) / max(0.1, self.g)))
        max_px = int(self.base_spd * air_frames * 0.85)
        max_tiles = max(2, min(8, max_px // TILE))

        for step in range(1, max_tiles + 1):
            tx = front_tx + dir * step
            landing_x = tx * TILE + (2 if dir > 0 else TILE - self.w - 2)
            if self.bounded and self._next_x_out_of_bounds(landing_x):
                break

            # 着地先は同じ高さだけでなく、少し低い足場も許容する。
            for drop in range(0, 3):
                ty = foot_ty + drop
                if not tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx, ty):
                    continue
                landing_y = ty * TILE - self.h
                if not self._hits_solid(landing_x, landing_y, level, TILES_X, TILES_Y):
                    return True, True
        return True, False

    def update(self, level=None, TILES_X=None, TILES_Y=None, player=None):
        self.stop_blocked = False
        target_dir = self.face
        if player is not None:
            target_dir = 1 if (player.x + player.w / 2) >= (self.x + self.w / 2) else -1
        if target_dir != self.prev_dir and self.on_ground:
            self.slide_timer = 10
            play_sfx_at("CHASER_SLIDE", self.x, self.y, self.w, self.h)
        self.prev_dir = target_dir
        self.face = target_dir

        if self._player_out_of_bounds(player):
            self.vx = 0
            self.stop_blocked = True
        elif self.slide_timer > 0:
            self.slide_timer -= 1
            self.vx *= 0.88
        else:
            game = Game._instance
            if game and getattr(game, "environment", "NONE") == "GRAVITY_ANOMALY":
                self.vx = self.base_spd * target_dir * GRAVITY_ANOMALY_MOVE_MULT
            elif game and getattr(game, "environment", "NONE") == "HIGH_GRAVITY":
                self.vx = self.base_spd * target_dir * HIGH_GRAVITY_MOVE_MULT
            else:
                self.vx = self.base_spd * target_dir

        if level is not None and TILES_X is not None and TILES_Y is not None:
            if self.on_ground and self.vx != 0:
                is_gap, can_jump = self._gap_jump_possible(level, TILES_X, TILES_Y, target_dir)
                if is_gap:
                    if can_jump:
                        game = Game._instance
                        if game and getattr(game, "environment", "NONE") == "GRAVITY_ANOMALY":
                            self.vy = self.jump_vy * GRAVITY_ANOMALY_JUMP_MULT
                        elif game and getattr(game, "environment", "NONE") == "HIGH_GRAVITY":
                            self.vy = self.jump_vy * HIGH_GRAVITY_JUMP_MULT
                        else:
                            self.vy = self.jump_vy
                        self.on_ground = False
                        play_sfx_at("ENEMY_JUMP", self.x, self.y, self.w, self.h)
                    else:
                        self.vx = 0
                        self.stop_blocked = True

            nx = self.x + self.vx
            if self._next_x_out_of_bounds(nx):
                nx = clamp(nx, self.left, self.right - self.w)
                self.vx = 0
                self.stop_blocked = True

            if self.vx != 0 and self._hits_solid(nx, self.y, level, TILES_X, TILES_Y):
                # 段差・障害物はホッパー相当ジャンプで越えようとする。
                if self.on_ground:
                    game = Game._instance
                    if game and getattr(game, "environment", "NONE") == "GRAVITY_ANOMALY":
                        self.vy = self.jump_vy * GRAVITY_ANOMALY_JUMP_MULT
                    elif game and getattr(game, "environment", "NONE") == "HIGH_GRAVITY":
                        self.vy = self.jump_vy * HIGH_GRAVITY_JUMP_MULT
                    else:
                        self.vy = self.jump_vy
                    self.on_ground = False
                    play_sfx_at("ENEMY_JUMP", self.x, self.y, self.w, self.h)
                else:
                    self.stop_blocked = True
                nx = self.x
            self.x = nx
        else:
            self.x += self.vx

        game = Game._instance
        if game and getattr(game, "environment", "NONE") == "GRAVITY_ANOMALY":
            self.vy += self.g * GRAVITY_ANOMALY_GRAVITY_MULT
        elif game and getattr(game, "environment", "NONE") == "HIGH_GRAVITY":
            self.vy += self.g * HIGH_GRAVITY_GRAVITY_MULT
        else:
            self.vy += self.g
        ny = self.y + self.vy
        self.on_ground = False
        if level is not None and TILES_X is not None and TILES_Y is not None:
            if self.vy >= 0:
                foot_y = ny + self.h
                ty = int(foot_y // TILE)
                tx_l = int((self.x + 2) // TILE)
                tx_r = int((self.x + self.w - 3) // TILE)
                hit = any(tile_is_ground_for_enemy(level, TILES_X, TILES_Y, tx, ty) for tx in (tx_l, tx_r))
                if hit:
                    ny = ty * TILE - self.h
                    self.vy = 0
                    self.on_ground = True
            elif self._hits_solid(self.x, ny, level, TILES_X, TILES_Y):
                self.vy = 0
                ny = self.y
        self.y = ny

    def damage(self, dmg):
        self.hp -= int(dmg)
        if self.hp <= 0:
            self.alive = False

    def draw(self):
        if self.stop_blocked:
            frame = 4
        elif not self.on_ground:
            frame = 3
        elif self.slide_timer > 0:
            frame = 2
        else:
            frame = (pyxel.frame_count // 6) % 2
        super().draw("CHASER_WALKER", frame)


class SplitImmortalFlyer(Flyer):
    """倒れず、被弾時に近くへ同種を1体増やすフライヤー。"""
    def __init__(self, x, y, left, right, spd=1, active=True, top=None, bottom=None):
        super().__init__(x, y, left, right, spd=spd, active=active, top=top, bottom=bottom)
        self.hit_flash_timer = 0

    def damage(self, dmg):
        self.hit_flash_timer = 30  # 0.5秒
        g = Game._instance
        if g is not None:
            ox = 16 if random.randint(0, 1) == 0 else -16
            nx = clamp(self.x + ox, 0, WORLD_W - self.w)
            ny = clamp(self.y, 0, stage_world_h(getattr(g, "stage", 1)) - self.h)
            # 縦長Stage9でも親と同じ上下範囲・行動方式を引き継ぐ。
            child = SplitImmortalFlyer(
                nx, ny,
                getattr(self, "left", nx - 48),
                getattr(self, "right", nx + 64),
                spd=abs(self.vx) or 1.0, active=True,
                top=getattr(self, "top", None), bottom=getattr(self, "bottom", None),
            )
            child.vx = -self.vx if self.vx != 0 else 1.0
            child.score_key = None
            child.score_hp = 1
            g.enemies.append(child)

    def update(self, player=None):
        if self.hit_flash_timer > 0:
            self.hit_flash_timer -= 1
        super().update(player)

    def draw(self):
        if not self.active:
            return
        if self.hit_flash_timer > 0 and (pyxel.frame_count // 3) % 2 == 0:
            return
        EnemyBase.draw(self, "SPLIT_FLYER", 0)


class AimShooter(Shooter):
    """プレイヤー方向へ斜めにも撃つ高速シューター。"""
    def __init__(self, x, y, bullet_speed=4.5, hp=3):
        super().__init__(x, y)
        self.hp = hp
        self.bullet_speed = bullet_speed

    def update(self, px=None, py=None, shoot_cb=None):
        if px is not None:
            self.face = 1 if px >= self.x else -1
        if self.shoot_cd > 0:
            self.shoot_cd -= 1
            return
        if shoot_cb is not None and px is not None and py is not None:
            sx = self.x + self.w / 2
            sy = self.y + self.h / 2
            dx = (px + 8) - sx
            dy = (py + 8) - sy
            dist = max(1.0, math.sqrt(dx * dx + dy * dy))
            vx = self.bullet_speed * dx / dist
            vy = self.bullet_speed * dy / dist
            shoot_cb(sx, sy, vx, vy)
        self.shoot_cd = random.randint(45, 120)

    def damage(self, dmg):
        self.hp -= int(dmg)
        if self.hp <= 0:
            self.alive = False

    def draw(self):
        super(Shooter, self).draw("AIM_SHOOTER", 0)

class Boss(EnemyBase):
    def __init__(self, x, y, hp=3, sprite_key="BOSS", is_midboss=False):
        super().__init__(x, y, 16, 16, 1.0)
        self.hp = hp
        self.sprite_key = sprite_key
        self.is_midboss = is_midboss
        # ステージ9専用中ボス(MID9)は通常色のまま。
        # ステージ9内に再登場する歴代中ボスは、生成時に別途反転フラグが設定される。
        if sprite_key == "MID9":
            self.stage9_invert_palette = False

    def update(self, left=32*TILE, right=WORLD_W - 32*TILE):
        self.x += self.vx

        # 端に来たら「反転だけ」ではなく、範囲内へ戻してから向きを確定する。
        # Stage9のTM2マーカー範囲では、更新後にclampされるため、
        # 反転前の向きが残ると右端/左端で止まったように見えることがあった。
        if self.x < left:
            self.x = left
            self.vx = abs(self.vx)
        elif self.x > right - self.w:
            self.x = right - self.w
            self.vx = -abs(self.vx)

        # 描画・ショット方向用。これが無いと、左移動中でも右向き絵/右向きショットになりやすい。
        if self.vx > 0:
            self.face = 1
        elif self.vx < 0:
            self.face = -1

    def damage(self, dmg):
        self.hp -= dmg
        if self.hp <= 0:
            self.alive = False

    def get_draw_state(self):
        """
        描画用の状態を返す。
        優先順位:
          1) 明示的にセットされた anim_state（FSM / update 由来）
          2) 速度・接地状態からの推定
          3) fallback: "stop"
        """
        state = getattr(self, "anim_state", None)

        # 一部のFSMでは「停止→突進」「着地停止」などの切替直後に、
        # 直前の anim_state が1フレーム以上残ることがある。
        # 特に Stage6/8 の突進は vx が出ている間は停止絵にしない。
        vx = abs(getattr(self, "vx", 0))
        vy = abs(getattr(self, "vy", 0))

        # Stage9 midboss draw guard:
        # 特殊行動後の停止/予備動作で、直前の jump anim_state が残ると
        # 停止中にジャンプ絵 (MID9 frame 3: 160,160) が出てしまう。
        # MID9 は停止専用絵 (frame 2: 224,64) を必ず使わせる。
        if self.sprite_key == "MID9" and state == "jump" and vx <= 0.1 and vy <= 0.1:
            return "stop"

        if state == "stop" and vx > 0.1 and self.sprite_key in ("BOSS6", "BOSS8"):
            return "charge" if getattr(self, "_ground_rush_draw", False) else "walk"
        if state:
            return state


        if vy > 0.1:
            return "jump"
        if vx > 0.1:
            return "walk"
        return "stop"

    def _draw_image_bank(self):
        """ボス/中ボスの描画元 Image 番号を返す。

        - Stage1-4 boss/mid: sekka.pyxres Image1
        - Stage5-8 boss: sekka.pyxres Image2
        - Stage5-9 midboss: sekka.pyxres Image0
        - Stage9 final boss: sekka3.pyxres Image1
        """
        if self.sprite_key == "FINAL":
            game = getattr(Game, "_instance", None) if "Game" in globals() else None
            if game is not None and hasattr(game, "_ensure_final_sprite_sheet_installed"):
                if game._ensure_final_sprite_sheet_installed():
                    return 2
            return 1

        origin_stage = getattr(self, "field_boss_origin_stage", None)
        if origin_stage is not None:
            try:
                st = int(origin_stage)
            except Exception:
                st = 1
            if getattr(self, "is_midboss", False):
                return 1 if st <= 4 else 0
            return 1 if st <= 4 else 2

        game = getattr(Game, "_instance", None) if "Game" in globals() else None
        try:
            st = int(getattr(game, "stage", 1))
        except Exception:
            st = 1

        if getattr(self, "is_midboss", False):
            return 1 if st <= 4 else 0
        if st >= 5:
            return 2
        return 1

    def _stage9_guarded_draw_key(self):
        """Stage9歴代ボス/中ボスの描画キーを出身ステージから固定する。

        AI・HP・当たり判定・行動状態には触れず、描画時だけガードする。
        これにより、何らかの一時状態で sprite_key がずれたり、
        不正な描画状態が残っても別ボスのUVを参照しない。
        """
        origin_stage = getattr(self, "field_boss_origin_stage", None)
        if origin_stage is None:
            return self.sprite_key
        try:
            st = int(origin_stage)
        except Exception:
            return self.sprite_key
        if not (1 <= st <= 8):
            return self.sprite_key
        return f"MID{st}" if getattr(self, "is_midboss", False) else f"BOSS{st}"

    def _draw_with_optional_resource_swap(self, frame, img, draw_key=None):
        """描画本体。

        Stage9歴代ボス/中ボスでは draw_key を出身ステージに固定し、
        他ボスのUVへ逸脱しないようにする。
        """
        key = draw_key or self.sprite_key
        super().draw(key, frame=frame, img=img)

    def draw(self):
        """
        Boss draw (state-driven).
        - 行動ロジックとは独立
        - BOSS_DRAW_RULES に従って描画フレームを決定
        - Stage9歴代ボス/中ボスは出身ステージの描画範囲だけに固定
        - 中ボス／通常ボス／ラスボスの全てへ常時1px黒輪郭を付ける
        """
        img = self._draw_image_bank()

        # Stage9再登場個体は、出身ステージから描画キーを強制決定。
        # 性能・AI・sprite_key本体は変更しない。
        draw_key = self._stage9_guarded_draw_key()

        rules = BOSS_DRAW_RULES.get(draw_key)
        if rules:
            state = self.get_draw_state()
            frames = rules.get(state) or rules.get("stop") or [0]
        else:
            frames = [0]

        # 最終ガード：
        # 選ばれたframeが、そのdraw_keyのCHAR_UV範囲外ならstop→0へ戻す。
        uv_frames = CHAR_UV.get(draw_key, [])
        valid_frames = [int(f) for f in frames
                        if isinstance(f, int) and 0 <= int(f) < len(uv_frames)]
        if not valid_frames:
            stop_frames = (BOSS_DRAW_RULES.get(draw_key, {}) or {}).get("stop") or [0]
            valid_frames = [int(f) for f in stop_frames
                            if isinstance(f, int) and 0 <= int(f) < len(uv_frames)]
        if not valid_frames:
            valid_frames = [0]

        if len(valid_frames) == 1:
            frame = valid_frames[0]
        else:
            frame = valid_frames[(pyxel.frame_count // 8) % len(valid_frames)]

        # 実座標・当たり判定には触れず、描画時だけ一時的に1pxずらす。
        old_x, old_y = self.x, self.y
        try:
            for col in range(1, 16):
                pyxel.pal(col, 0)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                self.x = old_x + dx
                self.y = old_y + dy
                self._draw_with_optional_resource_swap(frame, img, draw_key)
        finally:
            self.x, self.y = old_x, old_y
            pyxel.pal()

        # Stage9通常フィールド内に再登場する歴代ボスは、通常版と見分けやすいよう
        # 任意でパレット反転して描画できる。0番色は透明扱いのため反転対象から外す。
        if getattr(self, "stage9_invert_palette", False):
            try:
                for c in range(1, 16):
                    pyxel.pal(c, 16 - c)
                self._draw_with_optional_resource_swap(frame, img, draw_key)
            finally:
                pyxel.pal()
        else:
            self._draw_with_optional_resource_swap(frame, img, draw_key)

class Reaper(EnemyBase):
    def __init__(self):
        # ゴーストは通常サイズ敵と同じ 16x16。
        # 以前は幅12で描画していたため、CHAR_UV["REAPER"] の (48,128) から
        # 右端4pxが欠けて表示されていた。
        super().__init__(-999, -999, 16, 16, 0); self.active=False
    def spawn(self, px, py):
        self.x = px - 80; self.y = py - 60; self.active=True
    def update(self, px, py):
        if not self.active: return
        dx = 1 if px > self.x else -1
        dy = 1 if py > self.y else -1
        self.x += dx * 2.4; self.y += dy * 1.2
    def draw(self):
        if self.active:
            # 全場面で上下左右1pxの黒い輪郭影を付ける。
            try:
                for col in range(1, 16):
                    pyxel.pal(col, 0)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    draw_char_sprite("REAPER", self.x + dx, self.y + dy,
                                     self.w, self.h, 1)
            finally:
                pyxel.pal()
            draw_char_sprite("REAPER", self.x, self.y, self.w, self.h, 1)
# === ANCHOR END ===

# ===== プレイヤー =====
# === ANCHOR: PLAYER (DO NOT EDIT) ===
class Player:
    def __init__(self, x, y):
        self.base_w = 16; self.base_h = 16
        self.w = 16; self.h = 16
        self.x = x; self.y = y
        self.vx = 0; self.vy = 0
        self.on_ground = False
        self.alive = True
        self.armor = 0
        self.invincible_timer = 0
        self.pstate = "NONE"  # "NONE" / "ATTACK" / "ARMOR"
        self.power = 1
        self.shot_cd = 0
        self.coyote = 0
        self.jump_buf = 0
        self.head_hit_tiles = []
        self.face = 1  # 1:右, -1:左
        self._apex_hang = 0
        self.anim_t = 0        # 歩きアニメ用のタイマー
        self.anim_step = 0     # 0 or 1（2コマ歩き）
        self.prev_x = float(x)  # 前フレームのX位置を覚えておく
        self.is_walking = False
        self.walk_input_hold = 0
        self.ground_anim_timer = 0
        self.env_slide_vx = 0.0
        # 小数速度の端数を次フレームへ持ち越し、左右で同じ実効速度にする。
        self.x_move_remainder = 0.0
        self.pending_large_resize = False

    def set_size_keep_bottom(self, w, h):
        old_h = self.h
        self.w = w; self.h = h
        self.y -= (self.h - old_h)

    def try_set_size_keep_bottom_safe(self, w, h, level, TILES_X, TILES_Y):
        """拡大先が固形タイルと重なる場合は、ワープさせず拡大を保留する。"""
        if w <= self.w and h <= self.h:
            self.set_size_keep_bottom(w, h)
            self.pending_large_resize = False
            return True
        target_y = self.y - (h - self.h)
        l, r, t, b = rect_to_tiles(self.x, target_y, w, h)
        for ty in range(t, b + 1):
            for tx in range(l, r + 1):
                if is_solid_for_player(tile_at(level, TILES_X, TILES_Y, tx, ty)):
                    self.pending_large_resize = True
                    return False
        self.w = w; self.h = h; self.y = target_y
        self.pending_large_resize = False
        return True

    def update(self, level, TILES_X, TILES_Y, platforms):
        if not self.alive: return

        if self.pending_large_resize and self.pstate in ("ATTACK", "ARMOR"):
            self.try_set_size_keep_bottom_safe(32, 32, level, TILES_X, TILES_Y)

        if self.invincible_timer > 0:
            self.invincible_timer -= 1

        # 入力(横) - 空中は水平速度を sqrt(2) 倍
        game = Game._instance
        env = getattr(game, "environment", "NONE") if game else "NONE"
        spd = MOVE_SPD * (AIR_X_MULT if not self.on_ground else 1.0)
        if input_dash():
            spd *= DASH_X_MULT
        if not self.on_ground and self.armor > 0:
            spd *= POWER_JUMP_FACTOR
        input_dir = 0
        if input_left():
            input_dir = -1; self.face = -1
        if input_right():
            input_dir = 1; self.face = 1
        target_vx = float(input_dir) * spd
        if game:
            target_vx *= game.environment_x_multiplier(target_vx)
        if env == "GRAVITY_ANOMALY":
            target_vx *= GRAVITY_ANOMALY_MOVE_MULT
        elif env == "HIGH_GRAVITY":
            target_vx *= HIGH_GRAVITY_MOVE_MULT
        # 重力異常中だけ、低重力らしい緩やかな加速・減速を適用する。
        if env == "GRAVITY_ANOMALY":
            accel = 0.22 if self.on_ground else 0.12
            friction = 0.90 if self.on_ground else 0.97
            if input_dir:
                self.env_slide_vx += (target_vx - self.env_slide_vx) * accel
            else:
                self.env_slide_vx *= friction
                if abs(self.env_slide_vx) < 0.03:
                    self.env_slide_vx = 0.0
            self.vx = self.env_slide_vx
        # 雨・雪では地上だけでなく空中にも横慣性を残す。
        # 入力を離してもすぐには止まらず、ジャンプ着地後も滑り続ける。
        elif env in ("RAIN", "SNOW"):
            if self.on_ground:
                # 雨は「通常より少し滑る」程度。雪は旧・雨相当の慣性を残す。
                accel = 0.68 if env == "RAIN" else 0.32
                friction = 0.72 if env == "RAIN" else 0.93
            else:
                # 雨の空中慣性は軽め、雪は旧・雨相当で踏み切り時の勢いを維持する。
                accel = 0.38 if env == "RAIN" else 0.08
                friction = 0.90 if env == "RAIN" else 0.995

            if input_dir:
                self.env_slide_vx += (target_vx - self.env_slide_vx) * accel
            else:
                self.env_slide_vx *= friction
                if abs(self.env_slide_vx) < 0.03:
                    self.env_slide_vx = 0.0
            self.vx = self.env_slide_vx
        else:
            # 通常時は重力環境用の慣性処理を一切通さず、従来の即時入力速度を使う。
            self.vx = target_vx
            self.env_slide_vx = target_vx

        # --- 可変ジャンプ(Mario風) ---
        pressing = input_jump_held()
        rising   = (self.vy < 0)
        falling  = (self.vy > 0)

        # 頂点ふわっと(数フレームだけ重力を軽くする)
        if abs(self.vy) < 0.4:
            self._apex_hang = max(self._apex_hang, APEX_HANG_FRAMES)
        grav_mult = 1.0
        if rising:
            grav_mult = (JUMP_HOLD_GRAV_MULT if pressing else JUMP_RELEASE_GRAV_MULT)
        elif falling:
            grav_mult = FALL_GRAV_MULT
        if self._apex_hang > 0:
            grav_mult *= 0.85
            self._apex_hang -= 1

        add_g = GRAVITY * grav_mult
        if env == "GRAVITY_ANOMALY":
            add_g *= GRAVITY_ANOMALY_GRAVITY_MULT
        elif env == "HIGH_GRAVITY":
            add_g *= HIGH_GRAVITY_GRAVITY_MULT

        # 短跳び(ボタンを離したら上昇を早めに切る)
        if not pressing and self.vy < JUMP_CUT_VY:
            self.vy = JUMP_CUT_VY

        # ジャンプ発動(縦初速を sqrt(2) 倍)
        if self.jump_buf > 0 and (self.on_ground or self.coyote > 0):
            # 装備中(=size32)は縦初速を √1.1 倍 → 到達高さが約1.1倍に
            if env == "GRAVITY_ANOMALY":
                jump_mult = GRAVITY_ANOMALY_JUMP_MULT
            elif env == "HIGH_GRAVITY":
                jump_mult = HIGH_GRAVITY_JUMP_MULT
            else:
                jump_mult = 1.0
            self.vy = JUMP_VY * (POWER_JUMP_FACTOR if self.armor > 0 else 1.0) * jump_mult
            play_sfx("JUMP")
            self.on_ground = False
            self.jump_buf = 0

        # ジャンプ入力バッファ(キーはスペース据え置き)
        if input_jump_pressed():
            self.jump_buf = JUMPBUF_FRAMES

        # 射撃クールダウン
        if self.shot_cd > 0:
            self.shot_cd -= 1

        # X移動
        # int()の直接切り捨てでは、+方向の小数移動は遅く、-方向は速くなる。
        # 端数を持ち越して整数移動へ変換し、左右対称の実効速度にする。
        accumulated_dx = self.vx + self.x_move_remainder
        move_dx = int(accumulated_dx)
        self.x_move_remainder = accumulated_dx - move_dx
        self.x += move_dx
        l, r, t, b = rect_to_tiles(self.x, self.y, self.w, self.h)
        for ty in range(t, b + 1):
            for tx in range(l, r + 1):
                tt = tile_at(level, TILES_X, TILES_Y, tx, ty)
                if is_solid_for_player(tt):
                    if self.vx > 0:
                        self.x = tx * TILE - self.w
                    elif self.vx < 0:
                        self.x = (tx + 1) * TILE
                    # 壁に当たった端数を次フレームへ持ち越さない。
                    self.x_move_remainder = 0.0
                    if env in ("GRAVITY_ANOMALY", "RAIN", "SNOW"):
                        self.env_slide_vx = 0.0
                        self.vx = 0.0
        self.x = int(self.x)

        # Y移動
        self.vy += add_g
        # 落下し過ぎ防止の終端
        max_fall_speed = MAX_FALL_SPEED * (HIGH_GRAVITY_MAX_FALL_MULT if env == "HIGH_GRAVITY" else 1.0)
        if self.vy > max_fall_speed:
            self.vy = max_fall_speed
        self.y += self.vy
        l, r, t, b = rect_to_tiles(self.x, self.y, self.w, self.h)
        landed = False
        for ty in range(t, b + 1):
            for tx in range(l, r + 1):
                tt = tile_at(level, TILES_X, TILES_Y, tx, ty)
                # コイン取得
                if tt == TILE_COIN:
                    level[ty][tx] = EMPTY
                    Game._instance.add_score(100)
                    play_sfx("COIN")
                    put_kind(tx, ty, "AIR")
                if is_solid_for_player(tt):
                    if self.vy > 0:
                        self.y = ty * TILE - self.h
                        self.vy = 0
                        landed = True
                    elif self.vy < 0:
                        self.y = (ty + 1) * TILE
                        self.vy = 0
                        if tt in (TILE_BREAK, TILE_ITEM, TILE_BLOCK):
                            self.head_hit_tiles.append((tx, ty))
        self.y = int(self.y)

        # 低重力時だけ通常床の接地を1px補完し、停止絵と空中絵の交互表示を防ぐ。
        # 通常時はこの補完を通さないため、従来の接地・ジャンプ感覚に影響しない。
        if env == "GRAVITY_ANOMALY" and not landed and self.vy >= 0:
            foot_y = self.y + self.h
            ty_below = int(foot_y // TILE)
            tx_l = int((self.x + 1) // TILE)
            tx_r = int((self.x + self.w - 2) // TILE)
            for tx in range(tx_l, tx_r + 1):
                if is_solid_for_player(tile_at(level, TILES_X, TILES_Y, tx, ty_below)):
                    tile_top = ty_below * TILE
                    if 0 <= tile_top - foot_y <= 1:
                        self.y = tile_top - self.h
                        self.vy = 0
                        landed = True
                        break

        # 接地/コヨーテ
        if landed:
            self.on_ground = True
            self.coyote = COYOTE_FRAMES
        else:
            if self.coyote > 0: self.coyote -= 1
            self.on_ground = False

        # === ANCHOR: SPECIAL_FLOOR_TRIGGERS (OK TO EDIT) ===
        # 踏んだ床の特殊効果（KILL / SPRING）
        # ※ landed=True の時点で self.y は床上にスナップ済み
        if landed:
            foot_y = self.y + self.h + 1
            tx_l = int((self.x + 1) // TILE)
            tx_r = int((self.x + self.w - 2) // TILE)
            ty_f = int(foot_y // TILE)
            for tx in range(tx_l, tx_r + 1):
                tt = tile_at(level, TILES_X, TILES_Y, tx, ty_f)
                if tt == TILE_KILL:
                    if self.invincible_timer <= 0:
                        Game._instance.lose_life();
                        return
                elif tt == TILE_SPRING:
                    # 強制ジャンプ（入力不要）
                    # ★押し込み演出タイマー（踏んだ瞬間だけSPRING2表示）
                    Game._instance.spring_flash[(tx, ty_f)] = SPRING_PRESS_FRAMES
                    # 通常は低めの「ボヨン」。ジャンプキー入力中は「ボヨン」＋伸びる「ビヨーン」。
                    if input_jump_held() or self.jump_buf > 0:
                        play_sfx_at_ch(2, "SPRING_BOUNCE", tx * TILE, ty_f * TILE, TILE, TILE, margin=16)
                        play_sfx_at_ch(3, "SPRING_BIG", tx * TILE, ty_f * TILE, TILE, TILE, margin=16)
                    else:
                        play_sfx_at("SPRING_BOUNCE", tx * TILE, ty_f * TILE, TILE, TILE, margin=16)
                    self.vy = JUMP_VY * SPRING_JUMP_MULT
                    self.on_ground = False
                    self.coyote = 0
                    self.jump_buf = 0
                    break
        # === ANCHOR END ===

        # ジャンプ発動
        if self.jump_buf > 0 and (self.on_ground or self.coyote > 0):
            self.vy = JUMP_VY
            play_sfx("JUMP")
            self.on_ground = False
            self.jump_buf = 0

        # 動く足場(すり抜け防止:スイープ着地+ライド)
        landed_on_platform = False
        prev_y = self.y - self.vy   # 今フレームのY更新前の概算位置
        prev_bottom = prev_y + self.h
        now_bottom  = self.y + self.h

        ride_dx = 0
        ride_dy = 0

        for p in platforms:
            # 横方向重なりチェック(少し甘めの余白を持たせる)
            if (self.x + self.w > p.x - 1) and (self.x < p.x + p.w + 1):

                # 1) そのまま当たり(上から触れている)
                top_touch = (now_bottom >= p.y) and (now_bottom <= p.y + 6) and (self.vy >= p.dy_last - 0.1)

                # 2) スイープ判定(前フレーム→今フレームで上面を跨いだ)
                swept_cross = (prev_bottom <= p.y) and (now_bottom >= p.y) and (self.vy >= p.dy_last - 0.1)

                if (top_touch or swept_cross):
                    # 上面にスナップ
                    self.y = p.y - self.h
                    self.vy = 0
                    self.on_ground = True
                    landed_on_platform = True
                    ride_dx = p.dx_last      # 床の水平移動に“乗る”
                    # 垂直移動はスナップで吸収する。上昇床だけ少し余裕を持って追従
                    # ★ コンベア効果。AUTO本体またはMARK_CONVEYOR付きの動く床で流す。
                    if isinstance(p, Conveyor):
                        ride_dx += (p.spd if p.dir_right else -p.spd)
                        play_conveyor_machine_sfx_at(p.x, p.y, p.w, TILE)
                    elif getattr(p, "conveyor_spd", 0) > 0 and getattr(p, "conveyor_dir_right", None) is not None:
                        ride_dx += (p.conveyor_spd if p.conveyor_dir_right else -p.conveyor_spd)
                        play_conveyor_machine_sfx_at(p.x, p.y, p.w, TILE)
                    if p.dy_last < 0:  # 床が上がってきたときのめり込み防止
                        self.y += p.dy_last

        # 床の水平移動に乗る(横のすり抜け抑止)
        if landed_on_platform and ride_dx != 0:
            self.x += ride_dx
            # 乗った直後の壁めり込み解消(簡易)
            l, r, t, b = rect_to_tiles(self.x, self.y, self.w, self.h)
            for ty in range(t, b + 1):
                for tx in range(l, r + 1):
                    tt = tile_at(level, TILES_X, TILES_Y, tx, ty)
                    if is_solid_for_player(tt):
                        if ride_dx > 0:
                            self.x = tx * TILE - self.w
                        else:
                            self.x = (tx + 1) * TILE

        # 画面外落下(奈落)
        # これまでは固定の WORLD_H(=256px) を見ていたため、
        # Stage9 のように縦3画面分の広いフィールドでも、
        # 1画面目/2画面目の下端を越えた時点で奈落扱いになっていた。
        # Player.update() には現在ステージの TILES_Y が渡ってくるので、
        # 「そのステージ全体の一番下」だけを奈落にする。
        world_bottom = int(TILES_Y) * TILE
        if self.y >= world_bottom:
            self.alive = False
            self.death_cause = "void"
            return

        # === アニメ用の簡易接地タイマー更新 ===
        # 物理上は一瞬だけ「on_ground=False」になることがあるので、
        # 1〜2フレーム程度の浮きはアニメ上は「地上扱い」にして揺れを抑える
        if self.on_ground:
            self.ground_anim_timer = 0
        else:
            # 上限は適当にキャップしておく
            if self.ground_anim_timer < 60:
                self.ground_anim_timer += 1

        # ground_anim_timer <= 2 フレームまでは地上扱い
        anim_on_ground = (self.ground_anim_timer <= 2)

        # === 歩きアニメ更新（入力ベース・簡易安定版） ===
        # 「地上扱い ＋ 自分で左右入力しているとき」だけ歩き判定にする
        if anim_on_ground and abs(self.vx) > 0.5:
            self.walk_input_hold += 1
        else:
            self.walk_input_hold = 0

        # 2フレーム以上入力が続いたら「歩き中」とみなす（チャタリング防止）
        self.is_walking = (self.walk_input_hold >= 2)

        if self.is_walking:
            self.anim_t += 1
            if self.anim_t >= 8:     # 数字↑→アニメ速度調整
                self.anim_t = 0
                self.anim_step ^= 1  # 0 ⇔ 1 を反転（2コマ歩き）
        else:
            # 完全停止時は必ず 0 フレームに戻す
            self.anim_t = 0
            self.anim_step = 0

        # 今は dx 判定に使っていないが、将来の拡張用に残しておく
        self.prev_x = self.x

    def draw(self):
        # アニメ上の接地判定（1〜2フレームのズレは地上扱い）
        anim_on_ground = (self.ground_anim_timer <= 2)

        if not anim_on_ground:
            # 空中（ジャンプ／落下中）
            frame = 3
        else:
            # 地上
            if self.is_walking:
                frame = 1 + self.anim_step   # 1 ⇔ 2
            else:
                frame = 0   # 完全停止

        # 描画スプライト選択（効果・当たり判定は現状維持。ここは「見た目」だけ切り替える）
        if self.pstate == "ATTACK":
            # パワーアップ（現状の描画）
            spr = "PLAYER_BIG" if self.w == 32 else "PLAYER"
        elif self.pstate == "ARMOR":
            # アーマー（×1 / ×2 で見た目を分岐）
            # 32x32へのサイズアップ保留中は、32サイズ用スプライトを16x16で切り取らず
            # 通常サイズのプレイヤー描画を維持する。空間ができて実サイズが32になった時点で
            # ARMOR1 / ARMOR2 の描画へ切り替える。
            if self.w < 32 or self.h < 32:
                spr = "PLAYER"
            elif self.armor >= 2:
                spr = "PLAYER_ARMOR2"
            elif self.armor == 1:
                spr = "PLAYER_ARMOR1"
            else:
                spr = "PLAYER_A"  # 保険（ここには来ない想定）
        else:
            # 通常
            spr = "PLAYER"
        draw_char_sprite(spr, self.x, self.y, self.w, self.h, self.face, frame)

# === ANCHOR END ===

# ===== ユーティリティ:隠しギミック用の「踏めるかどうか」 =====
# === ANCHOR: SOLID_FOR_PLAYER (DO NOT EDIT) ===
def is_solid_for_player(tile_id):
    """TILE_GHOST は出現中のみ地面扱い"""
    if tile_id == TILE_GHOST:
        return (pyxel.frame_count // 90) % 2 == 0
    return tile_id in (SOLID, TILE_BLOCK, TILE_BREAK, TILE_ITEM, TILE_KILL, TILE_SPRING)
# === ANCHOR END ===

# === ANCHOR: SOLID_FOR_BULLET (OK TO EDIT) ===
def is_solid_for_bullet(tile_id):
    """弾が当たったら消えるタイル群(地形やブロック類)。壊さない。"""
    if tile_id == TILE_GHOST:
        # GHOST は出現中のみ当たり扱い
        return (pyxel.frame_count // 90) % 2 == 0
    return tile_id in (SOLID, TILE_BLOCK, TILE_BREAK, TILE_ITEM, TILE_DOOR, TILE_KILL, TILE_SPRING)
# === ANCHOR END ===
def is_solid_for_enemy_bullet(tile_id):
    """敵弾が当たったら消えるタイル群。BOSS扉(TILE_DOOR)は貫通させる。"""
    if tile_id == TILE_GHOST:
        return (pyxel.frame_count // 30) % 2 == 0
    return tile_id in (SOLID, TILE_BLOCK, TILE_BREAK, TILE_ITEM, TILE_KILL, TILE_SPRING)
# === ENEMY_BULLET_SOLID END ===

# ===== ステージレイアウト =====
# === ANCHOR: STAGE_DATA (OK TO EDIT) ===
# 16グリッドにスナップさせた動く床(x, y, w, left, right は16の倍数)
STAGE_PLATFORMS = {
    1: [(160, FLOOR_Y - 32, 32, 144, 240, 1)],
    2: [(224, FLOOR_Y - 64, 32, 192, 272, 1), (256, FLOOR_Y - 96, 32, 240, 304, 1)],
    3: [(304, FLOOR_Y - 64, 48, 272, 368, 1)],
    4: [(176, FLOOR_Y - 80, 48, 160, 224, 1), (384, FLOOR_Y - 64, 32, 352, 432, 1)],
    5: [(448, FLOOR_Y - 80, 48, 416, 496, 1)],
    6: [(176, FLOOR_Y - 96, 48, 160, 240, 1)],
    7: [
        ( 9*TILE, FLOOR_Y - 48, 64, 9*TILE - 24, 9*TILE + 88, 1 ),
        ( 13*TILE, FLOOR_Y - 48, 64, 13*TILE - 24, 13*TILE + 88, 1 ),
        ( 17*TILE, FLOOR_Y - 48, 64, 17*TILE - 24, 17*TILE + 88, 1 ),
        ( 21*TILE, FLOOR_Y - 48, 64, 21*TILE - 24, 21*TILE + 88, 1 ),
        ( 25*TILE, FLOOR_Y - 48, 64, 25*TILE - 24, 25*TILE + 88, 1 ),
        ( 29*TILE, FLOOR_Y - 48, 64, 29*TILE - 24, 29*TILE + 88, 1 ),
        ( 33*TILE, FLOOR_Y - 48, 64, 33*TILE - 24, 33*TILE + 88, 1 ),
        ( 37*TILE, FLOOR_Y - 48, 64, 37*TILE - 24, 37*TILE + 88, 1 ),
        ( 41*TILE, FLOOR_Y - 48, 64, 41*TILE - 24, 41*TILE + 88, 1 ),
        ('V', 14*TILE, FLOOR_Y - 80, 16, FLOOR_Y - 144, FLOOR_Y - 48, 1),
        ('V', 28*TILE, FLOOR_Y - 80, 16, FLOOR_Y - 144, FLOOR_Y - 48, 1),
        ('V', 38*TILE, FLOOR_Y - 80, 16, FLOOR_Y - 144, FLOOR_Y - 48, 1)
    ],
    8: [
        ('A',  10*TILE, FLOOR_Y - 64,  64,  8*TILE,  28*TILE, 1.6),
        ('A',  34*TILE, FLOOR_Y - 80,  48, 32*TILE,  44*TILE, 1.7),
        ('A',  46*TILE, FLOOR_Y - 96,  48, 44*TILE,  56*TILE, 1.8),
    ],
    9: [],
}

# コイン(タイル座標)
STAGE_COINS = {
    1: [(30, 23), (45, 22), (90, 20)],
    2: [(26, 22), (28, 21), (30, 20), (92, 20)],
    3: [(20, 18), (60, 17), (110, 16), (130, 16)],
    4: [(22, 19), (50, 18), (80, 17), (140,16)],
    5: [(18, 20), (19, 19), (21, 20), (92, 18)],
    6: [(35, 16), (60, 14), (90, 12), (120, 13)],
    7: [],
    8: [],
    9: [],
}
# === ANCHOR END ===

# ===== Game =====
# === ANCHOR: GAME_CLASS (DO NOT EDIT) ===
# === Boss Framework Scaffold (non-invasive) ===
# このブロックは「各ボスの個性付け」を容易にするための足場です。
# 既存のゲームプレイには影響しません（Game 側から呼ばない限り何もしません）。
# 使い方（例）:
#   from bosses import BossRegistry
#   self.boss = BossRegistry.create("rush", x, y)  # 使いたい時だけ
#
# ルール:
#  - BaseBoss: 共通インターフェース（update/attack/damage）
#  - 各ボスは BaseBoss を継承して振る舞いを実装
#  - BossRegistry: 文字列キーでボスを生成

import math

class BaseBoss:
    """共通ボス基底クラス（インターフェース）"""
    def __init__(self, x, y, hp=50, **kwargs):
        self.x, self.y = x, y
        self.w, self.h = kwargs.get("w", 32), kwargs.get("h", 32)
        self.hp = hp
        self.hp_max = hp
        self.alive = True
        self.vx = kwargs.get("vx", 0.0)
        self.vy = kwargs.get("vy", 0.0)
        self.state = "idle"
        self.meta = dict(kwargs)  # 各ボス固有のパラメータを保存

    # --- インターフェース（Game 側から呼ぶ想定） ---
    def update(self, left=0, right=240, top=0, bottom=136):
        """位置や状態の更新。必要に応じて継承側でオーバーライド。"""
        pass

    def attack(self):
        """攻撃（弾発射など）。必要に応じて継承側でオーバーライド。"""
        pass

    def damage(self, dmg: int):
        self.hp -= int(dmg)
        if self.hp <= 0:
            self.alive = False

    # --- ヘルパ（任意） ---
    def center(self):
        return (int(self.x + self.w // 2), int(self.y + self.h // 2))

# ---- 例: 体当たり（Rush）・ふわふわ（Float）※ロジック最小限の雛形 ----
class BossRush(BaseBoss):
    """体当たり突進型（雛形）。Game 側から呼ばない限り無効。"""
    def __init__(self, x, y, **kw):
        super().__init__(x, y, hp=kw.get("hp", 80), **kw)
        self.speed = kw.get("speed", 2.5)
        self.cooldown = 0
        self.direction = -1

    def update(self, left=0, right=240, top=0, bottom=136):
        if not self.alive:
            return
        # 雛形: X方向に移動して端で反転（最低限の例）
        self.x += self.speed * self.direction
        if self.x < left or self.x > right - self.w:
            self.direction *= -1
            self.x = max(left, min(right - self.w, self.x))

    def attack(self):
        # 雛形: ここに Game._instance.spawn_enemy_bullet(...) 等を書ける
        pass

class BossFloat(BaseBoss):
    """上下にふわふわ移動（雛形）。"""
    def __init__(self, x, y, **kw):
        super().__init__(x, y, hp=kw.get("hp", 60), **kw)
        self.amp = kw.get("amp", 8.0)
        self.freq = kw.get("freq", 0.10)
        self.base_y = y
        self.t = 0

    def update(self, left=0, right=240, top=0, bottom=136):
        if not self.alive:
            return
        self.t += 1
        self.y = self.base_y + math.sin(self.t * self.freq) * self.amp

    def attack(self):
        pass

# ---- Boss Registry ----
class BossRegistry:
    _map = {
        "rush": BossRush,
        "float": BossFloat,
    }

    @classmethod
    def register(cls, key: str, boss_cls):
        cls._map[key] = boss_cls

    @classmethod
    def create(cls, key: str, x: int, y: int, **kwargs) -> BaseBoss:
        boss_cls = cls._map.get(key)
        if boss_cls is None:
            raise KeyError(f"Unknown boss key: {key}")
        return boss_cls(x, y, **kwargs)
# === /Boss Framework Scaffold ===

@dataclass
class BossAction:
    fn: str
    duration: int = 0
    cooldown: int = 0
    args: Optional[Dict[str, Any]] = None

class BossFSM:
    def __init__(self,
                 actions: List[BossAction],
                 on_move_start: Optional[Callable[[float], None]] = None,
                 on_move_stop: Optional[Callable[[], None]] = None,
                 on_fanshot: Optional[Callable[[int, float], None]] = None,
                 on_jump_toward: Optional[Callable[[int, float, float, int], None]] = None,
                 # --- Stage3 など: 空中巡回 → 真下ショット → 突進/復帰 のような個性を足す ---
                 on_sky_patrol: Optional[Callable[[float, int, int, float], None]] = None,
                 on_sky_patrol_tick: Optional[Callable[[], None]] = None,
                 on_dive_to_player_floor: Optional[Callable[[float, int], None]] = None,
                 on_return_to_sky: Optional[Callable[[float, int], None]] = None,
                 on_ground_rush: Optional[Callable[[float, int, int], None]] = None,
                 on_random_action: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_stage7_edge_jump_start: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_stage7_edge_jump_tick: Optional[Callable[[], None]] = None):
        
        self.actions = actions[:] if actions else []
        self.index = 0
        self.timer = 0
        self.cooldown = 0
        self.on_move_start = on_move_start
        self.on_move_stop = on_move_stop
        self.on_fanshot = on_fanshot
        self.on_jump_toward = on_jump_toward

        # Stage3: 空中巡回/真下ショット/突進/復帰
        self.on_sky_patrol = on_sky_patrol
        self.on_sky_patrol_tick = on_sky_patrol_tick
        self.on_dive_to_player_floor = on_dive_to_player_floor
        self.on_return_to_sky = on_return_to_sky
        self.on_ground_rush = on_ground_rush
        self.on_random_action = on_random_action
        self.on_stage7_edge_jump_start = on_stage7_edge_jump_start
        self.on_stage7_edge_jump_tick = on_stage7_edge_jump_tick

        self._phase = "idle"  # "idle" | "act" | "cooldown"

    def update(self):
        if not self.actions:
            return

        current = self.actions[self.index]

        if self._phase == "idle":
            # enter action
            self.timer = int(current.duration or 0)
            self._phase = "act"
            self._enter_action(current)
            return

        if self._phase == "act":
            self._tick_action(current)
            self.timer -= 1
            if self.timer <= 0:
                # leave to cooldown phase
                self._leave_action(current)
                self.cooldown = int(current.cooldown or 0)
                self._phase = "cooldown"
            return

        if self._phase == "cooldown":
            self.cooldown -= 1
            if self.cooldown <= 0:
                # next action
                self.index = (self.index + 1) % len(self.actions)
                self._phase = "idle"
            return

    # ----- action handlers -----
    def _enter_action(self, action: BossAction):
        name = (action.fn or "").lower()

        # --- 既存 ---
        if name == "moveloop":
            args = action.args or {}
            spd = float(args.get("speed", 1.5))
            if self.on_move_start:
                self.on_move_start(spd)
            return

        if name in ("jumptowardplayer", "smalljump"):
            args = action.args or {}
            pre  = int(args.get("pre_stop", 12))
            xmul = float(args.get("x_mul", 2.0))
            ymul = float(args.get("y_mul", 2.0))
            land = int(args.get("land_stop", 30))
            if self.on_jump_toward:
                # Adapter側で現在アクションの args を参照し、
                # SmallJump中の接触ミス/無敵などを反映する。
                self.on_jump_toward(pre, xmul, ymul, land)

            # JumpToward/SmallJump はアクション時間を内部の微小FSMに委譲（即 cooldown へ）
            self._phase = "cooldown"
            self.cooldown = max(1, action.cooldown or 1)
            return

        if name == "groundrush":
            args = action.args or {}
            speed = float(args.get("speed", 4.0))
            duration = int(args.get("rush_frames", action.duration or 36))
            land_stop = int(args.get("land_stop", 8))
            if self.on_ground_rush:
                self.on_ground_rush(speed, duration, land_stop)
            self._phase = "cooldown"
            self.cooldown = max(1, action.cooldown or 1)
            return

        if name == "randomaction":
            args = action.args or {}
            if self.on_random_action:
                self.on_random_action(args)
            self._phase = "cooldown"
            self.cooldown = max(1, action.cooldown or 1)
            return

        if name == "stage7edgejump":
            args = action.args or {}
            if self.on_stage7_edge_jump_start:
                self.on_stage7_edge_jump_start(args)
            return

        if name == "fanshot":
            if self.on_move_stop:
                self.on_move_stop()

            args = action.args or {}

            # Stage6などの shield_only_stop ボスでは、扇ショット時の一時停止は
            # 「弱点の停止」ではなく「攻撃モーション」として扱う。
            # そのためショット中/クールダウン中も踏みダメージは通さない。
            if bool(args.get("shield_only_stop", False)):
                try:
                    g = Game._instance
                    boss = getattr(g, "boss", None) if g is not None else None
                    if boss is not None:
                        # Stage6 guard boss: 扇ショット中は「無敵」ではない。
                        # ただし弱点ではないので、踏んでもHPは減らない。
                        # invincible=True にすると接触処理側でミス扱いになりやすいため分離する。
                        setattr(boss, "invincible", False)
                        setattr(boss, "_stomp_vulnerable", False)
                        setattr(boss, "stomp_safe_when_invincible", True)
                        setattr(boss, "jump_contact_damage", False)
                except Exception:
                    pass

            ways = int(args.get("ways", 5))
            spread = float(args.get("spread", 30.0))

            if self.on_fanshot:
                self.on_fanshot(ways, spread)

            self._phase = "cooldown"
            self.cooldown = max(1, action.cooldown or 1)
            return

        # --- Stage3: 新規 ---
        if name == "skypatrol":
            # 空中巡回しつつ、一定間隔で真下ショット
            args = action.args or {}
            spd = float(args.get("speed", 1.6))
            sky_y = int(args.get("y", 48))
            shot_interval = int(args.get("shot_interval", 60))  # 60f=1sec
            shot_vy = float(args.get("shot_vy", 3.0))
            if self.on_sky_patrol:
                self.on_sky_patrol(spd, sky_y, shot_interval, shot_vy)
            return

        if name == "divetoplayerfloor":
            # 停止無しで、プレイヤー近くの床へ直線突進
            args = action.args or {}
            spd = float(args.get("speed", 6.0))
            x_margin = int(args.get("x_margin", 8))
            if self.on_dive_to_player_floor:
                self.on_dive_to_player_floor(spd, x_margin)
            return

        if name == "wait":
            # その場停止
            if self.on_move_stop:
                self.on_move_stop()
            return

        if name == "returntosky":
            args = action.args or {}
            spd = float(args.get("speed", 1.2))
            sky_y = int(args.get("y", 48))
            if self.on_return_to_sky:
                self.on_return_to_sky(spd, sky_y)
            return

    def _tick_action(self, action: BossAction):
        # per-tick hook (必要な行動だけ)
        name = (action.fn or "").lower()
        if name == "skypatrol":
            if self.on_sky_patrol_tick:
                self.on_sky_patrol_tick()
        elif name == "stage7edgejump":
            if self.on_stage7_edge_jump_tick:
                self.on_stage7_edge_jump_tick()
        # Dive/Return/Stage7EdgeJump は adapter 側の移動で「到達したら timer を短縮」して終了させる

    def _leave_action(self, action: BossAction):

        name = (action.fn or "").lower()
        if name == "moveloop":
            pass
        elif name == "jumptowardplayer":
            pass
        elif name == "fanshot":
            pass
        else:
            pass

# ============================================================================
# === ANCHOR: BOSS_KINDS (data-driven presets for bosses)
# ============================================================================

# --- Midboss presets (use same adapter; keep it simple for now) ---
# --- Midboss presets (use same adapter; keep it simple for now) ---
# --- Boss/Midboss presets (temporary defaults; will be expanded per stage) ---
# NOTE: In this file, BOSS_CONFIGS.update(...) was executed before BOSS_CONFIGS existed,
#       causing NameError. Define BOSS_CONFIGS as a single dict for now.
BOSS_CONFIGS = {
    # ---- Midboss 1..8 ----
    # 今回は「描画・撃破演出」は触らず、既存エネミーの大まかな行動だけ流用する。
    # stage1/7/8: Walker / stage2: Hopper / stage3: Shooter / stage4: Flyer
    # stage5: StompDamageWalker / stage6: NormalShotImmuneWalker
    "stage1_mid": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 1.54})],
    "stage2_mid": [BossAction(fn="MidHopper", duration=9999, cooldown=0, args={"speed": 0.8})],
    "stage3_mid": [BossAction(fn="MidShooter", duration=9999, cooldown=0, args={"shot_cd_min": 45, "shot_cd_max": 120, "hyper_shot": True})],
    "stage4_mid": [BossAction(fn="MidFlyer", duration=9999, cooldown=0, args={"speed": 1.4, "y": 48, "floor_explode": True, "down_vy": 0.35, "explode_frames": 30})],
    "stage5_mid": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 1.6, "stomp_damage": True})],
    "stage6_mid": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 1.7, "normal_shot_immune": True})],
    "stage7_mid": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 1.7, "fan_shot": True, "shot_cd_min": 90, "shot_cd_max": 150})],
    "stage8_mid": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 2.16, "rush": True, "rush_cd_min": 60, "rush_cd_max": 150, "rush_duration": 90, "rush_speed_mul": 2.0, "rush_prep_frames": 18, "rush_patterns": ["rush", "jump", "hyper3"], "jump_speed_mul": 1.45, "jump_vy": -7.2, "hyper3_interval": 15, "hyper3_speed": 3.4})],
    # Stage9 midboss: Stage8型をさらに10%高速化 + 通常ショット無効/反射
    "stage9_mid": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 2.376, "rush": True, "rush_cd_min": 54, "rush_cd_max": 135, "rush_duration": 90, "rush_speed_mul": 2.2, "rush_prep_frames": 18, "rush_patterns": ["rush", "jump", "hyper3"], "jump_speed_mul": 1.595, "jump_vy": -7.92, "hyper3_interval": 14, "hyper3_speed": 3.74, "normal_shot_immune": True, "reflect_normal_shot": True})],

    # ---- Boss 1..8 (temporary) ----
    "stage1_boss": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 1.6})],
    "stage2_boss": [
        # Stage2 boss: patrol -> stop -> jump -> stop の順序を明確にする。
        # pre_stop 中は BossAIAdapter 側で停止絵に固定する。
        BossAction(fn="MoveLoop", duration=120, cooldown=0, args={"speed": 1.4}),
        BossAction(fn="JumpTowardPlayer", duration=0, cooldown=180,
                   args={"pre_stop": 30, "x_mul": 2.0, "y_mul": 2.0, "land_stop": 30}),
    ],
    "stage3_boss": [
        # 行動1: 上空左右移動 + 1秒ごとに真下へ通常ショット（踏めない高さ）
        BossAction(fn="SkyPatrol", duration=240, cooldown=0,
                   args={"speed": 2.2, "y": 48, "shot_interval": 20, "shot_vy": 3.0}),
        # 行動2: 停止無しでプレイヤー近くの床へ直線突進
        BossAction(fn="DiveToPlayerFloor", duration=9999, cooldown=0,
                   args={"speed": 6.0, "x_margin": 8}),
        # 行動3: その場停止（約1秒）
        BossAction(fn="Wait", duration=120, cooldown=0),
        # 行動4: ゆっくり上空へ戻る → 行動1へループ
        BossAction(fn="ReturnToSky", duration=9999, cooldown=0,
                   args={"speed": 3.0, "y": 48}),
    ],
    "stage4_boss": [BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 1.2})],

    # ---- Boss 5..8: 既存FSM/ショット/ジャンプを組み合わせた後半ボス ----
    # Stage5: 踏むとミス。小ジャンプ頻度を下げ、プレイヤー方向への地上突進を主力にする。
    "stage5_boss": [
        BossAction(fn="MoveLoop", duration=110, cooldown=0, args={"speed": 1.82, "stomp_damage": True}),
        BossAction(fn="GroundRush", duration=0, cooldown=34,
                   args={"speed": 4.35, "rush_frames": 42, "land_stop": 8, "stomp_damage": True}),
        BossAction(fn="MoveLoop", duration=90, cooldown=0, args={"speed": 2.42, "stomp_damage": True}),
        BossAction(fn="JumpTowardPlayer", duration=0, cooldown=150,
                   args={"pre_stop": 8, "x_mul": 1.35, "y_mul": 1.10, "land_stop": 12, "stomp_damage": True}),
        BossAction(fn="GroundRush", duration=0, cooldown=30,
                   args={"speed": 4.65, "rush_frames": 48, "land_stop": 8, "stomp_damage": True}),
    ],

    # Stage6: ガード型。基本行動は「横移動 / 扇ショット / 小ジャンプ / 停止」。
    # HPが減るのは「明示的な停止アクション中に踏まれた時」だけ。
    # 小ジャンプ中は無敵 + 接触ミス。プレイヤーショット系は常時完全無効。
    "stage6_boss": [
        BossAction(fn="MoveLoop", duration=95, cooldown=0,
                   args={"speed": 2.74, "shield_only_stop": True, "shot_immune_all": True}),
        BossAction(fn="FanShot", duration=0, cooldown=34,
                   args={"ways": 3, "spread": 22.0, "speed": 2.85,
                         "shield_only_stop": True, "shot_immune_all": True}),
        BossAction(fn="RandomAction", duration=0, cooldown=23,
                   args={"stage6_jump_chain": True,
                         "shield_only_stop": True, "jump_contact_damage": True, "shot_immune_all": True}),
        BossAction(fn="Wait", duration=45, cooldown=0,
                   args={"shield_only_stop": True, "shot_immune_all": True}),
    ],

    # Stage7: 端固定で「既存扇ショットを微妙に角度を変えて3連射」
    # → 1秒停止 → 再び3連射 → 2秒停止 → 反対端へジャンプ → ループ。
    "stage7_boss": [
        BossAction(fn="FanShot", duration=0, cooldown=12,
                   args={"ways": 5, "spread": 42.0, "speed": 2.70, "angle_jitter": 3.0, "stage7_edge_lock": True}),
        BossAction(fn="FanShot", duration=0, cooldown=12,
                   args={"ways": 5, "spread": 42.0, "speed": 2.75, "angle_jitter": 3.0, "stage7_edge_lock": True}),
        BossAction(fn="FanShot", duration=0, cooldown=60,
                   args={"ways": 5, "spread": 46.0, "speed": 2.80, "angle_jitter": 4.0, "stage7_edge_lock": True}),

        BossAction(fn="FanShot", duration=0, cooldown=12,
                   args={"ways": 5, "spread": 42.0, "speed": 2.70, "angle_jitter": 3.0, "stage7_edge_lock": True}),
        BossAction(fn="FanShot", duration=0, cooldown=12,
                   args={"ways": 5, "spread": 42.0, "speed": 2.75, "angle_jitter": 3.0, "stage7_edge_lock": True}),
        BossAction(fn="FanShot", duration=0, cooldown=120,
                   args={"ways": 5, "spread": 46.0, "speed": 2.80, "angle_jitter": 4.0, "stage7_edge_lock": True}),

        # ジャンプ / ワープ3種を各210%で分岐。Stage7ボス専用。
        BossAction(fn="Stage7EdgeJump", duration=90, cooldown=0,
                   args={"frames": 54, "arc": 72, "random_warp": True, "warp_warn": 54}),
    ],

    # Stage8: 横移動をやめ、行動終了直後にランダムで次行動へ移る複合型。
    "stage8_boss": [
        # 各ランダム行動後に停止時間を置く。停止中のみダメージが通る。
        BossAction(fn="RandomAction", duration=0, cooldown=1,
                   args={"choices": ["fan5", "jump", "hyper3", "rush"], "speed_mul": 1.00, "shield_only_stop": True}),
        BossAction(fn="Wait", duration=42, cooldown=0, args={"shield_only_stop": True}),
    ],

    # ---- Stage9 final boss: HP残量で行動が変わる専用フェーズ制ラスボス ----
    # 実際の行動は BossAIAdapter._update_final_phase_boss() で制御する。
    "final_boss": [BossAction(fn="FinalPhaseBoss", duration=9999, cooldown=0, args={})],
}

# --- Stage boss definitions (single source of truth) ---
# sprite_key は仮。絵を描いたら CHAR_UV を増やして差し替えていく。
DEFAULT_MIDBOSS_DEF = {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID1",  "preset": "stage1_mid"}
DEFAULT_BOSS_DEF    = {"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS1", "preset": "stage1_boss"}
DEFAULT_FINAL_DEF   = {"hp": 60, "w": 64, "h": 64, "sprite_key": "FINAL", "preset": "final_boss"}

STAGE_BOSS_DEF = {
    1: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID1",  "preset": "stage1_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS1", "preset": "stage1_boss"}},

    2: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID2",  "preset": "stage2_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS2", "preset": "stage2_boss"}},

    3: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID3",  "preset": "stage3_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS3", "preset": "stage3_boss"}},

    4: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID4",  "preset": "stage4_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS4", "preset": "stage4_boss"}},

    5: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID5",  "preset": "stage5_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS5", "preset": "stage5_boss"}},

    6: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID6",  "preset": "stage6_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS6", "preset": "stage6_boss"}},

    7: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID7",  "preset": "stage7_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS7", "preset": "stage7_boss"}},

    8: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID8",  "preset": "stage8_mid"},
        "boss":{"hp": 30, "w": 64, "h": 64, "sprite_key": "BOSS8", "preset": "stage8_boss"}},

    # Stage9: 追加pyxres側のタイルマップ/ボス素材を使う想定。
    # ボス設定は後で作り込むため、HP等は通常ボス相当に戻す。
    9: {"mid": {"hp": 10, "w": 32, "h": 32, "sprite_key": "MID9",  "preset": "stage9_mid"},
        "boss":{"hp": 60, "w": 64, "h": 64, "sprite_key": "FINAL", "preset": "final_boss"}},

    # ラスボスは「ステージ8後に連戦」想定：ここでは定義だけしておく（出現トリガは後で配線）
    "final": {"boss": DEFAULT_FINAL_DEF},
}
#MID
#BOSS_CONFIGS: Dict[str, List[BossAction]] = {
#    "stage1_boss": [
#        BossAction(fn="MoveLoop", duration=9999, cooldown=0, args={"speed": 1.6}),
#    ],
#    "stage2_boss": [
#        BossAction(fn="MoveLoop", duration=120, cooldown=0, args={"speed": 1.4}),
#        BossAction(fn="JumpTowardPlayer", duration=0, cooldown=180,
#                   args={"pre_stop": 12, "x_mul": 2.0, "y_mul": 2.0, "land_stop": 30}),
#    ],
#}
# ============================================================================
# === ANCHOR: BOSS_FSM_USAGE_GUIDE (comment-only; no runtime effect)
# ============================================================================
"""
How to activate the FSM for Stage 1 (optional; keeps legacy default):
--------------------------------------------------------------------
1) Create an adapter when you spawn the boss in stage 1:
    self._boss_ai = BossAIAdapter(self, self.boss)
    self._boss_ai.load_preset("stage1_boss")

2) In your boss-scene update loop, call:
    if self._boss_ai: self._boss_ai.update()

3) Right after your legacy 'boss_stop_timer' hits 0 and before
   resuming movement, notify the adapter (optional):
    if self.boss_stop_timer == 0 and self._boss_ai:
        self._boss_ai.on_stop_cleared()

This wiring preserves your current behavior. Switch presets to change
personality per stage or to mid-boss by using "stage1_mid".
"""
class BossAIAdapter:
    """Bridge between Game and BossFSM; keeps existing game structure unchanged."""
    def __init__(self, game, boss):
        # Resolve BossFSM even if order changes (safety, no behavior change)
        try:
            FSM = BossFSM
        except NameError:
            from __main__ import BossFSM as FSM
        self.game = game
        self.boss = boss
        self.fsm = BossFSM(
            actions=[],
            on_move_start=self._on_move_start,
            on_move_stop=self._on_move_stop,
            on_fanshot=self._on_fanshot,
            on_jump_toward=self._on_jump_toward,

            # --- Stage3 personality hooks ---
            on_sky_patrol=self._on_sky_patrol,
            on_sky_patrol_tick=self._on_sky_patrol_tick,
            on_dive_to_player_floor=self._on_dive_to_player_floor,
            on_return_to_sky=self._on_return_to_sky,
            on_ground_rush=self._on_ground_rush,
            on_random_action=self._on_random_action,
            on_stage7_edge_jump_start=self._on_stage7_edge_jump_start,
            on_stage7_edge_jump_tick=self._on_stage7_edge_jump_tick,
        )

        # --- Stage3 runtime state (no effect unless preset uses it) ---
        self._mode = None              # "skypatrol" | "dive" | "return"
        self._shot_interval = 60
        self._shot_timer = 0
        self._shot_vy = 3.0
        self._sky_y = 48
        self._move_vx = 0.0
        self._move_vy = 0.0
        self._target_x = 0.0
        self._target_y = 0.0
        self._ground_rush_timer = 0
        self._ground_rush_land_stop = 0

        # --- Stage6 small-jump chain state ---
        # 連続小ジャンプは、ジャンプ関数を連続呼び出しすると状態が上書きされるため、
        # 「残り回数」を保持して着地後に次ジャンプを開始する。
        self._jump_chain_active = False
        self._jump_chain_remaining = 0
        self._jump_chain_total = 0
        self._jump_chain_done = 0
        self._jump_chain_pre_stop = 3
        self._jump_chain_x_muls = [0.85, 0.92, 0.99]
        self._jump_chain_y_muls = [0.72, 0.78, 0.84]
        self._jump_chain_land_stop = 0

        # --- Stage7 edge-loop runtime state ---
        self._stage7_side = "left"          # 反対端ジャンプ用の最後の端情報
        self._stage7_position = "left"      # 実際の待機位置: left / center / right
        self._stage7_jump_active = False
        self._stage7_jump_elapsed = 0
        self._stage7_jump_frames = 54
        self._stage7_jump_arc = 72.0
        self._stage7_jump_start_x = 0.0
        self._stage7_jump_start_y = 0.0
        self._stage7_jump_target_x = 0.0
        self._stage7_jump_target_y = 0.0
        self._stage7_jump_target_side = "right"
        self._stage7_warp_active = False
        self._stage7_warp_elapsed = 0
        self._stage7_warp_warn_frames = 54
        self._stage7_warp_target_x = 0.0
        self._stage7_warp_target_y = 0.0
        self._stage7_warp_target_pos = "left"

        # --- Stage4 runtime state (flyer-like move + summon + wrap) ---
        self._preset_name = ""
        self._summon_timer = 0
        self._summon_interval = 180   # 3 sec @ 60fps
        self._s4_base_vx = 1.2
        self._s4_base_down_vy = 0.35
        self._s4_base_rise_vy = 2.4
        self._s4_speed_mul = 1.0
        self._s4_down_vy = self._s4_base_down_vy
        self._s4_rise_vy = self._s4_base_rise_vy
        self._s4_pause_timer = 0
        self._s4_rising = False

        # --- Midboss personality runtime state (enemy-like behavior reuse) ---
        self._mid_kind = "walker"
        self._mid_jump_cd = 0
        self._mid_on_ground = False
        self._mid_shot_cd = 60
        self._mid_shot_cd_min = 45
        self._mid_shot_cd_max = 120

        # --- Midboss extra personality state ---
        self._mid_base_speed = 1.4
        self._mid_hyper_shot = False
        self._mid_fan_shot = False
        self._mid_rush_enabled = False
        self._mid_rush_timer = 0
        self._mid_rush_cd = 120
        self._mid_rush_cd_min = 120
        self._mid_rush_cd_max = 240
        self._mid_rush_duration = 45
        self._mid_rush_speed_mul = 2.0
        self._mid_rush_dir = 0
        self._mid_rush_state = "normal"
        self._mid_rush_prep_timer = 0
        self._mid_rush_prep_frames = 18
        self._mid_floor_explode = False
        self._mid_floor_explode_frames = 30
        self._mid_down_vy = 0.0
        self._mid_rush_patterns = ["rush"]
        self._mid_pending_action = "rush"
        self._mid_jump_speed_mul = 1.45
        self._mid_jump_vy = -7.2
        self._mid_hyper3_interval = 15
        self._mid_hyper3_speed = 3.4
        self._mid_hyper3_timer = 0
        self._mid_hyper3_count = 0

        # --- Stage9 final boss phase runtime state ---
        self._final_phase = 0
        self._final_action = "init"
        self._final_timer = 0
        self._final_sub_timer = 0
        self._final_burst_count = 0
        self._final_summon_cd = 120
        self._final_stage8_force_next_non_jump = False
        self._final_phase_transition_timer = 0
        self._final_phase_transition_frames = 30  # 約0.5秒@60fps
        self._final_phase_transition_timer = 0
        self._final_phase_transition_frames = 30  # 約0.5秒@60fps

    def load_preset(self, name: str):
        preset = BOSS_CONFIGS.get(name) or []
        self.fsm.actions = preset
        self.fsm.index = 0
        self.fsm._phase = "idle"
        self.fsm.cooldown = 0

        # 重要: ボス個性フラグはボスごとに必ず初期化（他ステージへ持ち越さない）
        setattr(self.boss, "invincible", False)
        setattr(self.boss, "_stomp_vulnerable", True)
        setattr(self.boss, "stomp_damage", False)
        setattr(self.boss, "normal_shot_immune", False)
        setattr(self.boss, "shot_immune_all", False)
        setattr(self.boss, "reflect_normal_shot", False)
        setattr(self.boss, "shield_only_stop", False)
        setattr(self.boss, "stomp_safe_when_invincible", False)
        setattr(self.boss, "jump_contact_damage", False)
        # 中ボスごとの移動処理差し替えフラグ。通常は従来どおり Boss.update を使う。
        setattr(self.boss, "_skip_default_midboss_update", False)

        # 中ボス追加個性フラグはプリセット読み込みごとに必ず初期化
        self._mid_base_speed = 1.4
        self._mid_hyper_shot = False
        self._mid_fan_shot = False
        self._mid_rush_enabled = False
        self._mid_rush_timer = 0
        self._mid_rush_cd = 120
        self._mid_rush_cd_min = 120
        self._mid_rush_cd_max = 240
        self._mid_rush_duration = 45
        self._mid_rush_speed_mul = 2.0
        self._mid_rush_dir = 0
        self._mid_rush_state = "normal"
        self._mid_rush_prep_timer = 0
        self._mid_rush_prep_frames = 18
        self._mid_floor_explode = False
        self._mid_floor_explode_frames = 30
        self._mid_down_vy = 0.0
        self._mid_rush_patterns = ["rush"]
        self._mid_pending_action = "rush"
        self._mid_jump_speed_mul = 1.45
        self._mid_jump_vy = -7.2
        self._mid_hyper3_interval = 15
        self._mid_hyper3_speed = 3.4
        self._mid_hyper3_timer = 0
        self._mid_hyper3_count = 0

        self._final_phase = 0
        self._final_action = "init"
        self._final_timer = 0
        self._final_sub_timer = 0
        self._final_burst_count = 0
        self._final_summon_cd = 120
        self._final_stage8_force_next_non_jump = False

        self._jump_chain_active = False
        self._jump_chain_remaining = 0
        self._jump_chain_total = 0
        self._jump_chain_done = 0
        self._jump_chain_pre_stop = 3
        self._jump_chain_x_muls = [0.85, 0.92, 0.99]
        self._jump_chain_y_muls = [0.72, 0.78, 0.84]
        self._jump_chain_land_stop = 0

        self._preset_name = str(name or "")
        if self._preset_name == "stage8_boss":
            # Stage8 random-action guard:
            # ジャンプ後、次のランダム行動で必ず非ジャンプを1回挟むための消費型フラグ。
            self._stage8_force_next_non_jump = False
            self._stage8_last_random_choice = None

        if self._preset_name == "stage7_boss":
            try:
                left = float(getattr(self.game, "boss_left", 0.0))
                right = float(getattr(self.game, "boss_right", left + globals().get("SCREEN_W", 256)))
                bw = float(getattr(self.boss, "w", 64))
                cx = float(getattr(self.boss, "x", left)) + bw * 0.5
                mid = (left + right) * 0.5
                self._stage7_side = "left" if cx <= mid else "right"
                self._stage7_position = self._stage7_side
                self.boss.x = self._stage7_position_x(self._stage7_position)
                self.boss.y = self._stage7_floor_y()
                self.boss.vx = 0.0
                self.boss.vy = 0.0
                self.boss.face = 1 if self._stage7_side == "left" else -1
                setattr(self.boss, "anim_state", "stop")
            except Exception:
                self._stage7_side = "left"
                self._stage7_position = "left"
            self._stage7_jump_active = False
            self._stage7_warp_active = False
            setattr(self.boss, "_final_phase_blink_timer", 0)

        # --- Midboss personality flags (only affects midboss presets) ---
        first_action = preset[0] if preset else None
        fn_name = ((getattr(first_action, "fn", "") or "").lower() if first_action else "")
        args = (getattr(first_action, "args", {}) or {}) if first_action else {}
        if self._preset_name.endswith("_mid"):
            if fn_name == "midhopper":
                self._mid_kind = "hopper"
                self._mid_jump_cd = 30
                self._mid_on_ground = False
                self.boss.vx = float(args.get("speed", 0.8))
            elif fn_name == "midshooter":
                self._mid_kind = "shooter"
                self.boss.vx = 0.0
                self.boss.vy = 0.0
                self._mid_shot_cd_min = int(args.get("shot_cd_min", 45))
                self._mid_shot_cd_max = int(args.get("shot_cd_max", 120))
                self._mid_shot_cd = random.randint(self._mid_shot_cd_min, self._mid_shot_cd_max)
                self._mid_hyper_shot = bool(args.get("hyper_shot", False))
            elif fn_name == "midflyer":
                self._mid_kind = "flyer"
                self.boss.vx = float(args.get("speed", 1.4))
                self.boss.vy = 0.0
                # Stage4中ボスだけ、通常Flyer.update相当の移動をAI側で完結させる。
                # その後の Game 側 Boss.update による固定移動で上書き/二重移動されないようにする。
                setattr(self.boss, "_skip_default_midboss_update", True)
                # Stage9フィールド配置版では、Stage4中ボスの固定Y(48)をそのまま使うと
                # マーカー位置から大きくずれるため、MARK_Aがあれば上端、無ければ現在位置を使う。
                if getattr(self.boss, "field_boss_stage", None) is not None:
                    self._mid_flyer_y_top = int(getattr(self.boss, "field_boss_top", getattr(self.boss, "y", 48)))
                else:
                    self._mid_flyer_y_top = int(args.get("y", 48))
                self._mid_floor_explode = bool(args.get("floor_explode", False))
                self._mid_floor_explode_frames = int(args.get("explode_frames", 30))
                self._mid_down_vy = float(args.get("down_vy", 0.0))
                self.boss.y = float(self._mid_flyer_y_top)
            else:
                self._mid_kind = "walker"
                self._mid_base_speed = float(args.get("speed", abs(getattr(self.boss, "vx", 1.4)) or 1.4))
                dir = 1 if float(getattr(self.boss, "vx", self._mid_base_speed)) >= 0 else -1
                self.boss.vx = dir * self._mid_base_speed

            self._mid_fan_shot = bool(args.get("fan_shot", False))
            self._mid_rush_enabled = bool(args.get("rush", False))
            self._mid_rush_cd_min = int(args.get("rush_cd_min", 120))
            self._mid_rush_cd_max = int(args.get("rush_cd_max", 240))
            self._mid_rush_duration = int(args.get("rush_duration", 45))
            self._mid_rush_speed_mul = float(args.get("rush_speed_mul", 2.0))
            self._mid_rush_prep_frames = int(args.get("rush_prep_frames", 18))
            patterns = args.get("rush_patterns", ["rush"])
            if isinstance(patterns, (list, tuple)) and patterns:
                self._mid_rush_patterns = [str(p) for p in patterns]
            else:
                self._mid_rush_patterns = ["rush"]
            self._mid_pending_action = "rush"
            self._mid_jump_speed_mul = float(args.get("jump_speed_mul", 1.45))
            self._mid_jump_vy = float(args.get("jump_vy", -7.2))
            self._mid_hyper3_interval = max(1, int(args.get("hyper3_interval", 15)))
            self._mid_hyper3_speed = float(args.get("hyper3_speed", 3.4))
            self._mid_hyper3_timer = 0
            self._mid_hyper3_count = 0
            self._mid_rush_timer = 0
            self._mid_rush_dir = 0
            self._mid_rush_state = "normal"
            self._mid_rush_prep_timer = 0
            self._mid_rush_cd = random.randint(self._mid_rush_cd_min, self._mid_rush_cd_max)
            if self._mid_rush_enabled:
                # Stage8中ボスなどの突進型は、通常Boss.updateとの二重移動を避け、
                # ここで「通常巡回→予備停止→突進→巡回復帰」を完結させる。
                setattr(self.boss, "_skip_default_midboss_update", True)
            if self._mid_fan_shot:
                self._mid_shot_cd_min = int(args.get("shot_cd_min", 90))
                self._mid_shot_cd_max = int(args.get("shot_cd_max", 150))
                self._mid_shot_cd = random.randint(self._mid_shot_cd_min, self._mid_shot_cd_max)

            if args.get("stomp_damage", False):
                setattr(self.boss, "stomp_damage", True)
            if args.get("normal_shot_immune", False):
                setattr(self.boss, "normal_shot_immune", True)
            if args.get("shot_immune_all", False):
                setattr(self.boss, "shot_immune_all", True)
            if args.get("reflect_normal_shot", False):
                setattr(self.boss, "reflect_normal_shot", True)

        # 通常ボス側にも、プリセットargsの基本フラグを反映する。
        # これで Stage6 boss などの「通常ショット無効」を中ボス専用にしない。
        if not self._preset_name.endswith("_mid"):
            for act in preset:
                a = getattr(act, "args", {}) or {}
                if a.get("normal_shot_immune", False):
                    setattr(self.boss, "normal_shot_immune", True)
                if a.get("shot_immune_all", False):
                    setattr(self.boss, "shot_immune_all", True)
                if a.get("reflect_normal_shot", False):
                    setattr(self.boss, "reflect_normal_shot", True)
                if a.get("stomp_damage", False):
                    setattr(self.boss, "stomp_damage", True)
                if a.get("shield_only_stop", False):
                    setattr(self.boss, "shield_only_stop", True)
                    setattr(self.boss, "stomp_safe_when_invincible", True)
                if a.get("jump_contact_damage", False):
                    setattr(self.boss, "jump_contact_damage", True)

        # Stage9に再配置した歴代Stage6ボスだけ、通常Stage6と同じ初期防御状態にする。
        # 最初のAI更新前にプレイヤーが接触しても、明示的なWait停止中以外ではHPを減らさない。
        if (int(getattr(self.game, "stage", 0)) == 9
                and int(getattr(self.boss, "field_boss_origin_stage", 0) or 0) == 6
                and not bool(getattr(self.boss, "is_midboss", False))):
            setattr(self.boss, "invincible", False)
            setattr(self.boss, "_stomp_vulnerable", False)
            setattr(self.boss, "stomp_safe_when_invincible", True)
            setattr(self.boss, "jump_contact_damage", False)

        self._summon_timer = self._summon_interval
        self._mode = None
        self._s4_pause_timer = 0
        self._s4_rising = False
        self._s4_speed_mul = 1.0
        if self._preset_name == "stage4_boss":
            # Stage4: flyer-like patrol + gentle descent
            self._s4_base_vx = 1.2
            self._s4_base_down_vy = 0.35
            self._s4_base_rise_vy = 2.4
            self._s4_down_vy = self._s4_base_down_vy
            self._s4_rise_vy = self._s4_base_rise_vy
            if hasattr(self.boss, "vx"):
                dir = 1 if getattr(self.boss, "vx", 1.0) >= 0 else -1
                self.boss.vx = dir * (self._s4_base_vx * self._s4_speed_mul)
            self.boss.vy = self._s4_down_vy
            # Stage9フィールド配置版では、画面最上段(0)ではなく
            # MARK_A/マーカー由来の上端から開始する。
            self.boss.y = float(getattr(self.boss, "field_boss_top", 0.0))
            setattr(self.boss, "invincible", False)
            setattr(self.boss, "_stomp_vulnerable", True)
            setattr(self.boss, "anim_state", "walk")

    def update(self):
        # Run FSM tick
        # Stage6の連続小ジャンプ中は、次アクションへ進ませると
        # Wait/MoveLoop等が割り込んで1回で終わるため、連続ジャンプ完了までFSMを止める。
        #
        # Stage8 boss fix:
        # RandomAction は「ジャンプ」「突進」などの内部 micro-FSM を起動した直後、
        # BossFSM 側ではすぐ cooldown/次アクションへ進む。
        # そのままだとジャンプ中・着地停止中・突進中に次の RandomAction/Wait が割り込み、
        #   ・ジャンプ後の禁止フラグが本当の着地前に消費される
        #   ・突進開始直後に Wait が vx=0 にして「ピクっ」だけで終わる
        #   ・結果として「ジャンプ→ジャンプ」が再発する
        # ため、Stage8 boss だけは内部行動が完全に終わるまで BossFSM を止める。
        stage8_internal_busy = False
        if self._preset_name == "stage8_boss":
            stage8_internal_busy = (
                bool(getattr(self, "_jump_state", None))
                or int(getattr(self, "_ground_rush_timer", 0)) > 0
                or int(getattr(self.game, "boss_stop_timer", 0)) > 0
            )

        if getattr(self.game, "paused", False):
            return

        # --- Stage9 final boss: HP残量で切り替わる専用フェーズ制 ---
        if self._preset_name == "final_boss":
            self._update_final_phase_boss()
            return

        if self.fsm and not getattr(self, "_jump_chain_active", False) and not stage8_internal_busy:
            self.fsm.update()

        # --- Midboss enemy-like personality (描画・撃破演出は既存のまま) ---
        if self._preset_name.endswith("_mid"):
            self._update_midboss_personality()

        # --- Stage4: flyer-like movement + summon + rise-to-top invincible ---
        if self._preset_name == "stage4_boss":
            # 通常ボス部屋では画面高、Stage9フィールド配置ではマーカー範囲の下端を使う。
            screen_h = float(getattr(self.boss, "field_boss_bottom", globals().get("SCREEN_H", 256)))
            top_y = float(getattr(self.boss, "field_boss_top", 0.0))
            boss_h = float(getattr(self.boss, "h", 64))

            if self._s4_rising:
                setattr(self.boss, "anim_state", "rise")
                setattr(self.boss, "invincible", True)
                setattr(self.boss, "_stomp_vulnerable", False)
                self.boss.vy = -abs(self._s4_rise_vy)
                self.boss.y = float(getattr(self.boss, "y", 0.0)) + float(self.boss.vy)
                if self.boss.y <= top_y:
                    self.boss.y = top_y
                    self._s4_rising = False
                    self._s4_speed_mul = min(2.0, float(self._s4_speed_mul) * 1.10)
                    self._s4_down_vy = self._s4_base_down_vy * self._s4_speed_mul
                    self._s4_rise_vy = self._s4_base_rise_vy * self._s4_speed_mul
                    if hasattr(self.boss, "vx"):
                        dir = 1 if getattr(self.boss, "vx", 1.0) >= 0 else -1
                        self.boss.vx = dir * (self._s4_base_vx * self._s4_speed_mul)
                    self.boss.vy = self._s4_down_vy
                    setattr(self.boss, "anim_state", "walk")
                    setattr(self.boss, "invincible", False)
                    setattr(self.boss, "_stomp_vulnerable", True)
            elif self._s4_pause_timer > 0:
                setattr(self.boss, "anim_state", "walk")
                self._s4_pause_timer -= 1
                self.boss.vy = 0.0
                setattr(self.boss, "invincible", False)
                setattr(self.boss, "_stomp_vulnerable", True)
            else:
                setattr(self.boss, "anim_state", "walk")
                setattr(self.boss, "invincible", False)
                setattr(self.boss, "_stomp_vulnerable", True)
                # 通常時は必ず上から下へ降りる。
                # 最下段到達時の上昇復帰以外では、フライヤー風の上下揺れはさせない。
                self.boss.vy = self._s4_down_vy
                self.boss.y = float(getattr(self.boss, "y", 0.0)) + float(self.boss.vy)

                if self.boss.y + boss_h >= screen_h:
                    self.boss.y = screen_h - boss_h
                    self._s4_rising = True
                    setattr(self.boss, "anim_state", "rise")
                    self.boss.vy = -abs(self._s4_rise_vy)
                    setattr(self.boss, "invincible", True)
                    setattr(self.boss, "_stomp_vulnerable", False)

            # 一定時間ごとに、雑魚フライヤーを 1〜3 体召喚
            # 出現位置は画面内の完全ランダム。ただしプレイヤーの近くには出さない。
            self._summon_timer -= 1
            if self._summon_timer <= 0:
                self._summon_timer = self._summon_interval
                count = random.randint(1, 3)
                # 通常ボス部屋は game.boss_left/right、Stage9フィールド配置版は
                # 個体ごとのMARK_L/R由来ワールド範囲を使う。
                left = float(getattr(self.boss, "field_boss_left", getattr(self.game, "boss_left", 0)))
                right = float(getattr(self.boss, "field_boss_right", getattr(self.game, "boss_right", left + globals().get("SCREEN_W", 256))))
                screen_h2 = float(getattr(self.boss, "field_boss_bottom", globals().get("SCREEN_H", 256)))
                top_y2 = float(getattr(self.boss, "field_boss_top", 0.0))

                # Stage9の歴代Stage4ボス限定：召喚元ボスを置いた256px区画から
                # フライヤーが上下の別ステージ区画へ移動しないよう、上下範囲を固定する。
                stage9_s4_section = None
                if (int(getattr(self.game, "stage", 0)) == 9
                        and int(getattr(self.boss, "field_boss_origin_stage", 0)) == 4
                        and not bool(getattr(self.boss, "is_midboss", False))):
                    stage9_s4_section = int(getattr(
                        self.boss, "stage9_section",
                        max(0.0, float(getattr(self.boss, "y", 0.0))) // float(SCREEN_H)
                    ))
                    section_top = float(stage9_s4_section * SCREEN_H)
                    section_bottom = section_top + float(SCREEN_H)
                    top_y2 = max(top_y2, section_top)
                    screen_h2 = min(screen_h2, section_bottom)
                    if screen_h2 <= top_y2:
                        top_y2, screen_h2 = section_top, section_bottom

                flyer_w = 16
                flyer_h = 16
                # 重要: boss_left / boss_right はワールド座標。
                # ここに SCREEN_W の画面座標を混ぜると x_max が 1 点に潰れて、
                # 召喚 X が固定されてしまう。
                # Stage9では行動範囲全体が縦長になるため、その全域から抽選すると
                # 召喚されても現在画面の外に出て「召喚していない」ように見える。
                # 現在のカメラ表示範囲とボスのMARK範囲が重なる部分へ必ず召喚する。
                cam_x = float(getattr(self.game, "cam_x", 0.0))
                cam_y = float(getattr(self.game, "cam_y", 0.0))
                visible_left = cam_x
                visible_right = cam_x + float(globals().get("SCREEN_W", 256))
                visible_top = cam_y
                visible_bottom = cam_y + float(globals().get("SCREEN_H", 256))
                # カメラとボス範囲が重なる時は画面内へ召喚する。
                # 重ならない時も、カメラ座標をそのまま採用せず必ずボス範囲内へ戻す。
                spawn_left = max(left, visible_left)
                spawn_right = min(right, visible_right)
                if spawn_right - spawn_left < flyer_w:
                    spawn_left, spawn_right = left, right

                spawn_top = max(top_y2, visible_top)
                spawn_bottom = min(screen_h2, visible_bottom)
                if spawn_bottom - spawn_top < flyer_h + 8:
                    spawn_top, spawn_bottom = top_y2, screen_h2

                x_min = int(spawn_left)
                x_max = int(max(x_min, spawn_right - flyer_w))
                y_min = int(spawn_top)
                y_max = int(max(y_min, spawn_bottom - flyer_h))
                p = self.game.player
                p_w = float(getattr(p, "w", 16))
                p_h = float(getattr(p, "h", 16))
                px = float(getattr(p, "x", 0.0)) + p_w * 0.5
                py = float(getattr(p, "y", 0.0)) + p_h * 0.5
                min_dist = max(p_w, p_h) * 4.0  # プレイヤー約4体分
                for _ in range(count):
                    fx = x_min
                    fy = y_min
                    found = False
                    for _try in range(24):
                        cand_x = random.randint(x_min, x_max)
                        cand_y = random.randint(y_min, y_max)
                        cx = float(cand_x) + flyer_w * 0.5
                        cy = float(cand_y) + flyer_h * 0.5
                        dx = cx - px
                        dy = cy - py
                        if dx * dx + dy * dy >= min_dist * min_dist:
                            fx = cand_x
                            fy = cand_y
                            found = True
                            break
                    if not found:
                        # フォールバック: プレイヤーから最短距離だけは確保する
                        ang = random.random() * math.pi * 2.0
                        radius = min_dist
                        fx = int(px + math.cos(ang) * radius - flyer_w * 0.5)
                        fy = int(py + math.sin(ang) * radius - flyer_h * 0.5)
                        fx = max(x_min, min(x_max, fx))
                        fy = max(y_min, min(y_max, fy))
                    patrol_left = max(left, fx - 48)
                    patrol_right = min(right, fx + 48 + flyer_w)
                    spd = 1.0 if random.random() < 0.5 else -1.0
                    # Stage9下層では通常Flyerの「WORLD_H(256)を越えたら消滅」が
                    # 即座に成立してしまう。上下範囲を明示して縦長ワールド用の
                    # 往復動作にし、召喚直後の消滅を防ぐ。
                    summon_top = spawn_top
                    summon_bottom = spawn_bottom
                    m = Flyer(
                        fx, fy, patrol_left, patrol_right, spd=spd, active=True,
                        top=summon_top, bottom=summon_bottom
                    )
                    m.vx = 1.0 * (1 if spd >= 0 else -1)
                    if int(getattr(self.game, "stage", 0)) == 9:
                        # Stage9だけ、Stage4ボス召喚フライヤーは最大8体。
                        # 9体目を追加する直前に最古の召喚個体を消す。
                        m.stage9_s4_summoned = True
                        # ボスの現在Yではなく、配置時に固定した区画を継承する。
                        # これにより上昇/下降中の召喚でも別区画へ所属がずれない。
                        if stage9_s4_section is not None:
                            m.stage9_section = int(stage9_s4_section)
                        else:
                            m.stage9_section = int((float(getattr(self.boss, "y", fy)) + float(getattr(self.boss, "h", 64)) * 0.5) // SCREEN_H)
                        old_summons = [
                            e for e in self.game.enemies
                            if getattr(e, "alive", False) and getattr(e, "stage9_s4_summoned", False)
                        ]
                        while len(old_summons) >= 8:
                            oldest = old_summons.pop(0)
                            oldest.alive = False
                            if oldest in self.game.enemies:
                                self.game.enemies.remove(oldest)
                    self.game.enemies.append(m)

        # --- Stage3: custom movement / shooting (only when preset uses Stage3 actions) ---
        if self._mode == "skypatrol":
            # keep boss at sky height (player can't stomp here)
            self.boss.y = float(self._sky_y)
            # horizontal is handled by Boss.update via boss.vx
        elif self._mode == "dive":
            # straight line to (target_x, target_y)
            self.boss.x = float(self.boss.x) + float(self._move_vx)
            self.boss.y = float(self.boss.y) + float(self._move_vy)

            # arrival check (overshoot-safe)
            if ((self._move_vx >= 0 and self.boss.x >= self._target_x) or (self._move_vx <= 0 and self.boss.x <= self._target_x)) and                ((self._move_vy >= 0 and self.boss.y >= self._target_y) or (self._move_vy <= 0 and self.boss.y <= self._target_y)):
                self.boss.x = float(self._target_x)
                self.boss.y = float(self._target_y)
                self._mode = None
                # 次フレームでアクションが終わるように短縮（1フレ遅れでOK）
                if getattr(self.fsm, "_phase", "") == "act":
                    self.fsm.timer = min(getattr(self.fsm, "timer", 0), 1)

        elif self._mode == "return":
            # move only in Y back to sky
            self.boss.y = float(self.boss.y) + float(self._move_vy)
            if (self._move_vy <= 0 and self.boss.y <= self._target_y) or (self._move_vy >= 0 and self.boss.y >= self._target_y):
                self.boss.y = float(self._target_y)
                self._mode = None
                if getattr(self.fsm, "_phase", "") == "act":
                    self.fsm.timer = min(getattr(self.fsm, "timer", 0), 1)

        # Drive ground rush micro-FSM (Stage5 / Stage8 random action)
        if getattr(self, "_ground_rush_timer", 0) > 0:
            self._ground_rush_timer -= 1
            setattr(self.boss, "anim_state", "charge")
            play_boss_rush_sfx_at(self.boss)
            if self._ground_rush_timer <= 0:
                if hasattr(self.boss, "vx"):
                    self.boss.vx = 0.0
                if hasattr(self.game, "boss_stop_timer"):
                    self.game.boss_stop_timer = max(getattr(self.game, "boss_stop_timer", 0), int(getattr(self, "_ground_rush_land_stop", 0)))
                if getattr(self.boss, "shield_only_stop", False):
                    setattr(self.boss, "invincible", False)
                    setattr(self.boss, "_stomp_vulnerable", True)
                    setattr(self.boss, "stomp_safe_when_invincible", True)
                    setattr(self.boss, "jump_contact_damage", False)
                setattr(self.boss, "anim_state", "stop")
                setattr(self.boss, "_ground_rush_draw", False)

        # Drive jump micro-FSM (only active when JumpTowardPlayer is engaged)
        if getattr(self, "_jump_state", None):
            if self._jump_state == "pre":
                self._jump_pre -= 1
                if self._jump_pre <= 0:
                    # clear stop and launch
                    if hasattr(self.game, "boss_stop_timer"):
                        self.game.boss_stop_timer = 0
                    pcx = self.game.player.x + getattr(self.game.player, "w", 16)/2
                    bcx = self.boss.x + getattr(self.boss, "w", 16)/2
                    dir = 1 if pcx >= bcx else -1
                    base = abs(getattr(self.boss, "vx", 1.0)) or 1.0
                    self.boss.vx = dir * base * self._jump_x_mul
                    jy = float(globals().get("JUMP_VY", -9.0))
                    self.boss.vy = jy * self._jump_y_mul

                    # Stage9再配置版のStage2ボスだけ、ジャンプ開始時のプレイヤー位置を
                    # 着地点として狙う。現在のY位置・初速・重力から滞空時間を逆算し、
                    # その時間でプレイヤー中央へ届く水平速度を設定する。
                    if bool(getattr(self, "_stage9_stage2_aim_landing", False)):
                        g = max(0.001, float(globals().get("GRAVITY", 0.5)))
                        boss_h = float(getattr(self.boss, "h", 64))
                        boss_w = float(getattr(self.boss, "w", 64))
                        floor_y = float(getattr(
                            self.boss, "field_boss_ground_y",
                            float(globals().get("FLOOR_Y", 208))
                        ))
                        target_top_y = floor_y - boss_h
                        y0 = float(getattr(self.boss, "y", target_top_y))
                        vy0 = float(getattr(self.boss, "vy", 0.0))
                        disc = max(0.0, vy0 * vy0 - 2.0 * g * (y0 - target_top_y))
                        flight_frames = max(1.0, (-vy0 + math.sqrt(disc)) / g)

                        player_center_x = (
                            float(getattr(self.game.player, "x", 0.0))
                            + float(getattr(self.game.player, "w", 16)) * 0.5
                        )
                        target_x = player_center_x - boss_w * 0.5
                        left = float(getattr(self.boss, "field_boss_left", target_x))
                        right = float(getattr(self.boss, "field_boss_right", target_x + boss_w))
                        target_x = clamp(target_x, left, right - boss_w)
                        self.boss.vx = (target_x - float(self.boss.x)) / flight_frames

                    if getattr(self.boss, "shield_only_stop", False):
                        setattr(self.boss, "invincible", True)
                        setattr(self.boss, "_stomp_vulnerable", False)
                        setattr(self.boss, "stomp_safe_when_invincible", not bool(getattr(self, "_jump_contact_damage", False)))
                        setattr(self.boss, "jump_contact_damage", bool(getattr(self, "_jump_contact_damage", False)))
                    setattr(self.boss, "anim_state", "jump")
                    # ジャンプ発射音。
                    # Stage6 boss はロケット発射風の長い「シュゴーーーー」を使う。
                    # 他ボスは従来どおり通常ジャンプ音を維持する。
                    if self._preset_name == "stage6_boss":
                        play_sfx_at_ch(2, "STAGE6_ROCKET", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
                    elif self._preset_name == "stage7_boss":
                        # Stage7 boss: 実際に浮き上がる瞬間だけ、軽い浮遊音を鳴らす。
                        play_sfx_at_ch(3, "STAGE7_FLOAT_JUMP", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
                    elif self._preset_name == "stage2_boss":
                        # Stage2ボスは通常ステージ・Stage9再配置版とも大ジャンプ音を使用する。
                        play_sfx_at_ch(3, "BOSS_BIG_JUMP", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
                    else:
                        play_sfx_at_ch(2, "ENEMY_JUMP", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
                    self._jump_state = "air"
            elif self._jump_state == "air":
                setattr(self.boss, "anim_state", "jump")
                g = float(globals().get("GRAVITY", 0.5))
                self.boss.vy = float(getattr(self.boss, "vy", 0.0)) + g
                self.boss.y = float(self.boss.y) + self.boss.vy
                # Stage9フィールド配置版では、通常ボス部屋の固定FLOOR_Yへ
                # 強制着地させると下層のボスが画面上方へワープしてしまう。
                # 個体ごとのマーカー由来接地Yを優先する。
                floor_y = int(getattr(self.boss, "field_boss_ground_y", globals().get("FLOOR_Y", 184)))
                h = int(getattr(self.boss, "h", 32))
                if self.boss.y + h >= floor_y:
                    self.boss.y = floor_y - h
                    self.boss.vy = 0.0
                    play_sfx_at("BOSS_LAND", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
                    if hasattr(self.game, "boss_stop_timer"):
                        self.game.boss_stop_timer = max(getattr(self.game, "boss_stop_timer", 0), self._jump_land)
                    # 着地後停止中は必ず停止絵。Stage5の小ジャンプ後にジャンプ絵が残るのを防ぐ。
                    setattr(self.boss, "anim_state", "stop")
                    if getattr(self.boss, "shield_only_stop", False):
                        if self._preset_name == "stage8_boss":
                            # Stage8 boss:
                            # ジャンプ後の 1.5秒停止は「攻撃後のスキ」なので、
                            # 通常の Wait 停止と同じく踏みダメージを通す。
                            # ただしジャンプ中の接触ミスだけはここで解除する。
                            setattr(self.boss, "invincible", False)
                            setattr(self.boss, "_stomp_vulnerable", True)
                            setattr(self.boss, "stomp_safe_when_invincible", True)
                            setattr(self.boss, "jump_contact_damage", False)
                        else:
                            # Stage6 guard boss:
                            # 小ジャンプの着地停止は「弱点の停止」ではない。
                            # 明示的な Wait アクション中だけ _stomp_vulnerable=True にする。
                            setattr(self.boss, "invincible", False)
                            setattr(self.boss, "_stomp_vulnerable", False)
                            setattr(self.boss, "stomp_safe_when_invincible", True)
                            setattr(self.boss, "jump_contact_damage", False)
                    self._jump_state = "land"
            elif self._jump_state == "land":
                if getattr(self.game, "boss_stop_timer", 0) > 0:
                    setattr(self.boss, "anim_state", "stop")
                if getattr(self.game, "boss_stop_timer", 0) <= 0:
                    if getattr(self, "_jump_chain_active", False) and getattr(self, "_jump_chain_remaining", 0) > 0:
                        # 着地後すぐに次の小ジャンプへ。2回目・3回目は少し高く遠くへ。
                        self._start_next_stage6_chain_jump()
                    else:
                        self._jump_state = None
                        self._jump_chain_active = False
                        self._jump_chain_remaining = 0
                        self._jump_chain_total = 0
                        self._jump_chain_done = 0

    def on_stop_cleared(self):
        # Placeholder for future use; no behavior change
        return

    def _update_midboss_personality(self):
        """中ボス専用：既存エネミーの大まかな行動だけをBossへ流用する。"""
        kind = getattr(self, "_mid_kind", "walker")

        if kind == "hopper":
            # Hopper流用：横移動は既存の Boss.update に任せ、ここではジャンプ/重力だけ足す。
            if self._mid_on_ground and self._mid_jump_cd <= 0:
                self.boss.vy = -4.0 * globals().get("JUMP_VY_MULT", 1.0)
                self._mid_jump_cd = 60
                self._mid_on_ground = False
                play_sfx_at("ENEMY_JUMP", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
            elif self._mid_jump_cd > 0:
                self._mid_jump_cd -= 1

            was_air = not bool(getattr(self, "_mid_on_ground", True))
            self.boss.vy = float(getattr(self.boss, "vy", 0.0)) + 0.3
            self.boss.y = float(getattr(self.boss, "y", 0.0)) + float(self.boss.vy)

            floor_y = int(getattr(self.boss, "field_boss_ground_y", globals().get("FLOOR_Y", 208)))
            bh = int(getattr(self.boss, "h", 32))
            if self.boss.y + bh >= floor_y:
                self.boss.y = floor_y - bh
                self.boss.vy = 0.0
                if was_air:
                    play_sfx_at("BOSS_LAND", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
                self._mid_on_ground = True

        elif kind == "shooter":
            # Shooter流用：その場でプレイヤー方向を向き、水平弾を撃つ。
            self.boss.vx = 0.0
            self.boss.vy = 0.0
            if getattr(self.game, "player", None) is not None:
                px = float(getattr(self.game.player, "x", 0.0))
                self.boss.face = 1 if px >= float(getattr(self.boss, "x", 0.0)) else -1

            self._mid_shot_cd -= 1
            if self._mid_shot_cd <= 0:
                face = int(getattr(self.boss, "face", 1))
                bx = float(self.boss.x) + (float(getattr(self.boss, "w", 32)) if face > 0 else -8)
                by = float(self.boss.y) + float(getattr(self.boss, "h", 32)) / 2

                if getattr(self, "_mid_hyper_shot", False):
                    # Stage3中ボス：プレイヤーのハイパーショット相当
                    # Bullet自体は共通クラスを使い、縦長・power=2・kind="power"にする。
                    big = Bullet(bx, by, 3 * face, power=2)
                    big.kind = "power"
                    big.tag = "midboss"
                    big.w = 6
                    big.h = 30
                    big.y = by - big.h // 2
                    self.game.enemy_bullets.append(big)
                    play_sfx_at("CHARGE_SHOT", bx, by, getattr(big, "w", 6), getattr(big, "h", 30), margin=24)
                else:
                    if hasattr(self.game, "spawn_enemy_bullet"):
                        self.game.spawn_enemy_bullet(bx, by, 3 * face)

                self._mid_shot_cd = random.randint(self._mid_shot_cd_min, self._mid_shot_cd_max)

        elif kind == "walker":
            # Walker流用：横移動は Game側の Boss.update に任せる。
            # ここでは Stage7の扇状ショット、Stage8の短時間突進だけ追加する。
            if getattr(self.game, "player", None) is not None:
                if getattr(self, "_mid_rush_enabled", False):
                    left = int(getattr(self.boss, "field_boss_left", int(globals().get("WORLD_W", 4096)) - 240))
                    right = int(getattr(self.boss, "field_boss_right", int(globals().get("WORLD_W", 4096)) - 64))
                    bw = int(getattr(self.boss, "w", 32))
                    bh = int(getattr(self.boss, "h", 32))
                    floor_y = int(getattr(self.boss, "field_boss_ground_y", globals().get("FLOOR_Y", 208)))
                    ground_y = floor_y - bh
                    state = getattr(self, "_mid_rush_state", "normal")

                    def _boss_center():
                        return (
                            float(getattr(self.boss, "x", 0.0)) + float(getattr(self.boss, "w", 32)) / 2,
                            float(getattr(self.boss, "y", 0.0)) + float(getattr(self.boss, "h", 32)) / 2,
                        )

                    def _player_center():
                        p = self.game.player
                        return (
                            float(getattr(p, "x", 0.0)) + float(getattr(p, "w", 16)) / 2,
                            float(getattr(p, "y", 0.0)) + float(getattr(p, "h", 16)) / 2,
                        )

                    def _spawn_hyper_to_player():
                        bx, by = _boss_center()
                        px, py = _player_center()
                        dx = px - bx
                        dy = py - by
                        dist = math.sqrt(dx * dx + dy * dy) or 1.0
                        spd = max(0.1, float(getattr(self, "_mid_hyper3_speed", 3.4)))
                        vx = spd * dx / dist
                        vy = spd * dy / dist

                        shot = Bullet(bx - 5, by - 5, vx, power=2, vy=vy)
                        shot.kind = "power"
                        shot.tag = "midboss"
                        shot.w = 10
                        shot.h = 10
                        shot.max_range = 360
                        self.game.enemy_bullets.append(shot)
                        play_sfx_at("CHARGE_SHOT", bx, by, getattr(shot, "w", 10), getattr(shot, "h", 10), margin=24)

                    def _resume_normal(prefer_dir=None):
                        # 特殊行動後は「プレイヤー方向」を引きずらず、行動範囲内の単純往復へ戻す。
                        if prefer_dir is None:
                            prefer_dir = int(getattr(self, "_mid_rush_dir", 0)) or (1 if float(getattr(self.boss, "vx", 1.0)) >= 0 else -1)
                        self._mid_rush_state = "normal"
                        self._mid_rush_timer = 0
                        self._mid_rush_prep_timer = 0
                        self._mid_rush_dir = 0
                        self._mid_pending_action = "rush"
                        self._mid_hyper3_timer = 0
                        self._mid_hyper3_count = 0
                        self.boss.vy = 0.0
                        self.boss.y = min(float(getattr(self.boss, "y", ground_y)), ground_y)
                        self.boss.x = clamp(float(getattr(self.boss, "x", left)), left, right - bw)
                        self._mid_rush_cd = random.randint(self._mid_rush_cd_min, self._mid_rush_cd_max)
                        self.boss.vx = (1 if prefer_dir >= 0 else -1) * self._mid_base_speed
                        self.boss.face = 1 if self.boss.vx >= 0 else -1
                        setattr(self.boss, "invincible", False)
                        setattr(self.boss, "_stomp_vulnerable", True)

                    if state == "prep":
                        # 特殊行動直前に一瞬停止。停止後、選ばれた行動へ移行する。
                        setattr(self.boss, "anim_state", "stop")
                        self.boss.vx = 0.0
                        self.boss.vy = 0.0
                        setattr(self.boss, "invincible", False)
                        setattr(self.boss, "_stomp_vulnerable", True)
                        self._mid_rush_prep_timer -= 1
                        if self._mid_rush_prep_timer <= 0:
                            action = str(getattr(self, "_mid_pending_action", "rush"))
                            if action == "jump":
                                self._mid_rush_state = "jump"
                                self._mid_rush_timer = 120
                                self.boss.vx = self._mid_rush_dir * self._mid_base_speed * float(getattr(self, "_mid_jump_speed_mul", 1.45))
                                self.boss.vy = float(getattr(self, "_mid_jump_vy", -7.2))
                                self.boss.face = self._mid_rush_dir
                                setattr(self.boss, "invincible", True)
                                setattr(self.boss, "_stomp_vulnerable", False)
                            elif action == "hyper3":
                                self._mid_rush_state = "hyper3"
                                self._mid_hyper3_timer = 1
                                self._mid_hyper3_count = 0
                                self.boss.vx = 0.0
                                self.boss.vy = 0.0
                                setattr(self.boss, "invincible", False)
                                setattr(self.boss, "_stomp_vulnerable", True)
                            else:
                                self._mid_rush_state = "rush"
                                self._mid_rush_timer = self._mid_rush_duration
                                self.boss.vx = self._mid_rush_dir * self._mid_base_speed * self._mid_rush_speed_mul
                                self.boss.face = self._mid_rush_dir
                                play_boss_rush_sfx_at(self.boss)

                    elif state == "rush":
                        setattr(self.boss, "anim_state", "charge")
                        play_boss_rush_sfx_at(self.boss)
                        rush_dir = int(getattr(self, "_mid_rush_dir", 0)) or (1 if float(getattr(self.boss, "vx", 1.0)) >= 0 else -1)
                        setattr(self.boss, "invincible", False)
                        setattr(self.boss, "_stomp_vulnerable", True)
                        self.boss.vx = rush_dir * self._mid_base_speed * self._mid_rush_speed_mul
                        self.boss.face = rush_dir
                        self.boss.x = float(getattr(self.boss, "x", 0.0)) + float(self.boss.vx)

                        # 突進は行動範囲の端に到達した時点で終了し、通常巡回へ戻す。
                        if rush_dir < 0 and float(self.boss.x) <= left:
                            self.boss.x = left
                            _resume_normal(prefer_dir=1)
                        elif rush_dir > 0 and float(self.boss.x) >= right - bw:
                            self.boss.x = right - bw
                            _resume_normal(prefer_dir=-1)
                        else:
                            self._mid_rush_timer -= 1
                            if self._mid_rush_timer <= 0:
                                _resume_normal(prefer_dir=rush_dir)

                    elif state == "jump":
                        # プレイヤー方向ジャンプ。ジャンプ中は無敵、接触はプレイヤーミス扱い。
                        setattr(self.boss, "anim_state", "jump")
                        setattr(self.boss, "invincible", True)
                        setattr(self.boss, "_stomp_vulnerable", False)
                        jump_dir = int(getattr(self, "_mid_rush_dir", 0)) or (1 if float(getattr(self.boss, "vx", 1.0)) >= 0 else -1)
                        self.boss.face = jump_dir
                        self.boss.vy = float(getattr(self.boss, "vy", 0.0)) + float(globals().get("GRAVITY", 0.5))
                        self.boss.x = float(getattr(self.boss, "x", 0.0)) + float(getattr(self.boss, "vx", 0.0))
                        self.boss.y = float(getattr(self.boss, "y", 0.0)) + float(getattr(self.boss, "vy", 0.0))

                        # 通常巡回範囲を超えないよう、左右端で止めて横速度を殺す。
                        if float(self.boss.x) <= left:
                            self.boss.x = left
                            self.boss.vx = 0.0
                        elif float(self.boss.x) >= right - bw:
                            self.boss.x = right - bw
                            self.boss.vx = 0.0

                        self._mid_rush_timer -= 1
                        if float(self.boss.y) >= ground_y or self._mid_rush_timer <= 0:
                            self.boss.y = ground_y
                            _resume_normal(prefer_dir=jump_dir)

                    elif state == "hyper3":
                        # 停止したまま、プレイヤー方向へハイパーショットを3連射。
                        setattr(self.boss, "anim_state", "stop")
                        self.boss.vx = 0.0
                        self.boss.vy = 0.0
                        setattr(self.boss, "invincible", False)
                        setattr(self.boss, "_stomp_vulnerable", True)
                        px = float(getattr(self.game.player, "x", 0.0))
                        self.boss.face = 1 if px >= float(getattr(self.boss, "x", 0.0)) else -1

                        self._mid_hyper3_timer -= 1
                        if self._mid_hyper3_count < 3 and self._mid_hyper3_timer <= 0:
                            _spawn_hyper_to_player()
                            self._mid_hyper3_count += 1
                            self._mid_hyper3_timer = int(getattr(self, "_mid_hyper3_interval", 15))

                        if self._mid_hyper3_count >= 3 and self._mid_hyper3_timer <= 1:
                            _resume_normal(prefer_dir=self.boss.face)

                    else:
                        # 基本行動：プレイヤー位置に関係なく、元の行動範囲を単純往復。
                        setattr(self.boss, "anim_state", "walk")
                        setattr(self.boss, "invincible", False)
                        setattr(self.boss, "_stomp_vulnerable", True)
                        dir = 1 if float(getattr(self.boss, "vx", self._mid_base_speed)) >= 0 else -1
                        self.boss.vx = dir * self._mid_base_speed
                        self.boss.face = dir
                        self.boss.y = ground_y
                        self.boss.vy = 0.0
                        self.boss.x = float(getattr(self.boss, "x", 0.0)) + float(self.boss.vx)
                        if float(self.boss.x) <= left:
                            self.boss.x = left
                            self.boss.vx = abs(self._mid_base_speed)
                            self.boss.face = 1
                        elif float(self.boss.x) >= right - bw:
                            self.boss.x = right - bw
                            self.boss.vx = -abs(self._mid_base_speed)
                            self.boss.face = -1

                        self._mid_rush_cd -= 1
                        if self._mid_rush_cd <= 0:
                            px = float(getattr(self.game.player, "x", 0.0))
                            face = 1 if px >= float(getattr(self.boss, "x", 0.0)) else -1
                            patterns = getattr(self, "_mid_rush_patterns", ["rush"]) or ["rush"]
                            action = random.choice(patterns)
                            if action not in ("rush", "jump", "hyper3"):
                                action = "rush"
                            self._mid_pending_action = action
                            self._mid_rush_dir = face
                            self.boss.face = face
                            self.boss.vx = 0.0
                            self.boss.vy = 0.0
                            self._mid_rush_state = "prep"
                            self._mid_rush_prep_timer = max(1, int(getattr(self, "_mid_rush_prep_frames", 18)))

                if getattr(self, "_mid_fan_shot", False):
                    self._mid_shot_cd -= 1
                    if self._mid_shot_cd <= 0:
                        bx = float(self.boss.x) + float(getattr(self.boss, "w", 32)) / 2
                        by = float(self.boss.y) + float(getattr(self.boss, "h", 32)) / 2
                        player_cx = float(self.game.player.x) + float(getattr(self.game.player, "w", 16)) / 2
                        player_cy = float(self.game.player.y) + float(getattr(self.game.player, "h", 16)) / 2
                        base_ang = math.atan2(player_cy - by, player_cx - bx)
                        speed = 2.2
                        for deg in (-20, -10, 0, 10, 20):
                            rad = base_ang + math.radians(deg)
                            vx = speed * math.cos(rad)
                            vy = speed * math.sin(rad)
                            if hasattr(self.game, "spawn_enemy_bullet"):
                                self.game.spawn_enemy_bullet(bx, by, vx, vy, tag="midboss")
                        self._mid_shot_cd = random.randint(self._mid_shot_cd_min, self._mid_shot_cd_max)

        elif kind == "flyer":
            # Flyer流用：通常エネミー Flyer.update と同じ流れを、Boss用サイズのまま再現する。
            # 描画・撃破演出・当たり判定サイズは触らず、移動だけをここで完結させる。
            left = int(getattr(self.boss, "field_boss_left", int(globals().get("WORLD_W", 4096)) - 240))
            right = int(getattr(self.boss, "field_boss_right", int(globals().get("WORLD_W", 4096)) - 64))
            bw = int(getattr(self.boss, "w", 32))

            self.boss.x = float(getattr(self.boss, "x", 0.0)) + float(getattr(self.boss, "vx", 0.0))
            if self.boss.x < left:
                self.boss.x = left
                self.boss.vx = abs(float(getattr(self.boss, "vx", 1.4)))
            elif self.boss.x > right - bw:
                self.boss.x = right - bw
                self.boss.vx = -abs(float(getattr(self.boss, "vx", 1.4)))

            # 通常Flyerのふわふわ移動に、Stage4用のゆっくり下降を足す。
            prev_y = float(getattr(self.boss, "y", 0.0))
            self.boss.y = (prev_y
                           + pyxel.sin(pyxel.frame_count * 0.1) * 0.5
                           + float(getattr(self, "_mid_down_vy", 0.0)))
            top = int(getattr(self.boss, "field_boss_top", getattr(self, "_mid_flyer_y_top", 48)))
            bottom = int(getattr(self.boss, "field_boss_ground_y", globals().get("FLOOR_Y", 208))) - int(getattr(self.boss, "h", 32))

            # Stage9のStage4歴代中ボスだけは、MARK_Uや配置マーカー由来のY座標を
            # 「床到達」とみなさない。以前はこの座標へ達しただけで、実際には空中でも
            # 自爆していた。Stage9では、真下にある実タイル／動く床の上面へ本当に
            # 接触した瞬間だけ自爆させる。通常Stage4の座標式自爆仕様は維持する。
            is_stage9_mid4 = (
                int(getattr(self.game, "stage", 0)) == 9
                and int(getattr(self.boss, "field_boss_origin_stage", 0) or 0) == 4
                and bool(getattr(self.boss, "is_midboss", False))
            )

            if getattr(self, "_mid_floor_explode", False):
                if is_stage9_mid4:
                    h = int(getattr(self.boss, "h", 32))
                    w = int(getattr(self.boss, "w", 32))
                    prev_foot = prev_y + h
                    next_foot = float(self.boss.y) + h
                    floor_y = None

                    # 現在位置の真下にある最初の実地形を探す。
                    level = getattr(self.game, "level", None)
                    tiles_x = int(getattr(self.game, "TILES_X", 0) or 0)
                    tiles_y = int(getattr(self.game, "TILES_Y", 0) or 0)
                    if level is not None and tiles_x > 0 and tiles_y > 0:
                        tx_l = max(0, int((float(self.boss.x) + 2) // TILE))
                        tx_r = min(tiles_x - 1, int((float(self.boss.x) + w - 3) // TILE))
                        start_ty = max(0, int(max(0.0, prev_foot) // TILE))
                        for ty in range(start_ty, tiles_y):
                            if any(is_solid_for_player(tile_at(level, tiles_x, tiles_y, tx, ty))
                                   for tx in range(tx_l, tx_r + 1)):
                                floor_y = float(ty * TILE)
                                break

                    # 動く床も実際に接触する床として扱う。
                    for platform in getattr(self.game, "platforms", []) or []:
                        px = float(getattr(platform, "x", 0.0))
                        py = float(getattr(platform, "y", 0.0))
                        pw = float(getattr(platform, "w", TILE))
                        horizontal_overlap = (float(self.boss.x) + w > px
                                              and float(self.boss.x) < px + pw)
                        if horizontal_overlap and py >= prev_foot - 1.0:
                            if floor_y is None or py < floor_y:
                                floor_y = py

                    if floor_y is not None:
                        # 後段のStage9共通Yクランプが、実床より上で止めないよう更新する。
                        self.boss.field_boss_ground_y = int(round(floor_y))
                        self.boss.field_boss_bottom = max(
                            int(getattr(self.boss, "field_boss_bottom", 0) or 0),
                            int(round(floor_y)),
                        )
                        # 上から床面を横切ったフレームだけを本当の床接触とする。
                        if next_foot >= floor_y and prev_foot <= floor_y + 1.0:
                            self.boss.y = floor_y - h
                            if hasattr(self.game, "start_midboss_explosion_effect"):
                                self.game.start_midboss_explosion_effect(
                                    self.boss, getattr(self, "_mid_floor_explode_frames", 30)
                                )
                            return
                    else:
                        # 真下に床が無い場合は、マーカー境界で空中停止・自爆しない。
                        self.boss.field_boss_bottom = max(
                            int(getattr(self.boss, "field_boss_bottom", 0) or 0),
                            int(stage_world_h(9)),
                        )
                elif self.boss.y >= bottom:
                    self.boss.y = bottom
                    if hasattr(self.game, "start_midboss_explosion_effect"):
                        self.game.start_midboss_explosion_effect(self.boss, getattr(self, "_mid_floor_explode_frames", 30))
                    return

            if is_stage9_mid4:
                # 実床接触までは下降を続ける。上端とステージ最下端だけ安全制限する。
                self.boss.y = clamp(self.boss.y, top, stage_world_h(9) - int(getattr(self.boss, "h", 32)))
            else:
                self.boss.y = clamp(self.boss.y, top, bottom)


    # ---- Stage3 callbacks ----
    def _on_sky_patrol(self, speed: float, sky_y: int, shot_interval: int, shot_vy: float):
        # horizontal patrol
        self._mode = "skypatrol"
        # Stage3: 行動1(上空)は無敵 + 触れるとプレイヤー側がダメージ
        setattr(self.boss, "invincible", True)
        setattr(self.boss, "_stomp_vulnerable", False)
        self._sky_y = int(sky_y)
        self._shot_interval = max(1, int(shot_interval))
        self._shot_timer = 0
        self._shot_vy = float(shot_vy)

        # keep current direction if any
        if hasattr(self.boss, "vx"):
            dir = 1 if getattr(self.boss, "vx", 1.0) >= 0 else -1
            self.boss.vx = dir * float(speed)

        # force sky height immediately.
        # Stage9フィールド配置版では、ボス部屋用の固定 sky_y ではなく
        # MARK_A/U から得た上端を基準にする。
        if getattr(self.boss, "field_boss_stage", None) is not None:
            self._sky_y = int(getattr(self.boss, "field_boss_top", self._sky_y))
        self.boss.y = float(self._sky_y)

        # animation hint
        setattr(self.boss, "anim_state", "walk")

    def _on_sky_patrol_tick(self):
        # shoot straight down every interval frames
        self._shot_timer += 1
        if self._shot_timer >= self._shot_interval:
            self._shot_timer = 0
            # boss center-bottom
            bx = float(self.boss.x) + float(getattr(self.boss, "w", 64)) / 2 - 3
            by = float(self.boss.y) + float(getattr(self.boss, "h", 64)) - 2
            if hasattr(self.game, "spawn_enemy_bullet"):
                # ステージ9で再登場しても、出身がStage3なら接地・壁接触で爆発する専用弾を維持する。
                origin_stage = int(getattr(self.boss, "field_boss_origin_stage", 0) or 0)
                is_stage3_boss = (self._preset_name == "stage3_boss" or origin_stage == 3)
                shot_tag = "stage3_boss_explosive" if is_stage3_boss else "boss"
                self.game.spawn_enemy_bullet(bx, by, 0, self._shot_vy, tag=shot_tag)

    def _on_dive_to_player_floor(self, speed: float, x_margin: int):
        # Stage3: 突進/停止中は無敵解除（踏み/被弾を通す）
        setattr(self.boss, "invincible", False)
        setattr(self.boss, "_stomp_vulnerable", True)
        # stop Boss.update horizontal influence and drive by adapter
        if hasattr(self.boss, "vx"):
            self.boss.vx = 0.0

        # target: near player's x, on floor.
        # Stage9フィールド配置版では、ボス部屋用の FLOOR_Y/boss_left/right ではなく
        # マーカー指定された足元Yと左右範囲を使う。
        floor_y = int(getattr(self.boss, "field_boss_ground_y", int(globals().get("FLOOR_Y", 208))))
        bw = float(getattr(self.boss, "w", 64))
        bh = float(getattr(self.boss, "h", 64))
        left = float(getattr(self.boss, "field_boss_left",
                             getattr(self.game, "boss_left", float(globals().get("WORLD_W", 0)) - 240)))
        right = float(getattr(self.boss, "field_boss_right",
                              getattr(self.game, "boss_right", float(globals().get("WORLD_W", 0)) - 16)))

        px_center = float(getattr(self.game.player, "x", 0)) + float(getattr(self.game.player, "w", 16))/2
        tx = px_center - bw/2
        tx = max(left + float(x_margin), min((right - bw) - float(x_margin), tx))

        ty = float(floor_y) - bh

        # compute direction vector
        sx = float(self.boss.x)
        sy = float(self.boss.y)
        dx = tx - sx
        dy = ty - sy
        dist = math.sqrt(dx*dx + dy*dy) or 1.0
        spd = max(0.1, float(speed))
        self._move_vx = dx / dist * spd
        self._move_vy = dy / dist * spd
        self._target_x = tx
        self._target_y = ty
        self._mode = "dive"

        # ラスボスの空中巡回→降下だけは、突進絵ではなくジャンプ/降下専用絵を使う。
        # Stage3系ボスの通常急降下は従来どおり charge を維持。
        if self._preset_name == "final_boss" or getattr(self.boss, "sprite_key", "") == "FINAL":
            setattr(self.boss, "anim_state", "jump")
        else:
            setattr(self.boss, "anim_state", "charge")

    def _on_return_to_sky(self, speed: float, sky_y: int):
        # Stage3: 停止→上昇開始（復帰中）はボス無敵。接触したらプレイヤーがダメージ
        setattr(self.boss, "invincible", True)
        setattr(self.boss, "_stomp_vulnerable", False)
        # return vertically to sky height
        if hasattr(self.boss, "vx"):
            self.boss.vx = 0.0

        if getattr(self.boss, "field_boss_stage", None) is not None:
            sky_y = int(getattr(self.boss, "field_boss_top", sky_y))
        self._target_y = float(int(sky_y))
        sy = float(self.boss.y)
        dy = self._target_y - sy
        spd = max(0.1, float(speed))
        self._move_vy = -spd if dy < 0 else spd
        self._mode = "return"

        setattr(self.boss, "anim_state", "walk")

    # ---- Callbacks expected by the FSM ----
    def _on_move_start(self, speed: float):
        # Restore horizontal motion; keep current direction if any.
        if hasattr(self.boss, "vx"):
            dir = 1 if getattr(self.boss, "vx", 1.0) >= 0 else -1
            self.boss.vx = dir * float(speed)
        if getattr(self.boss, "shield_only_stop", False):
            # Stage6 guard boss: 横移動中は「無敵」ではなく、単に弱点ではないだけ。
            # 上から踏めば他ボス同様に跳ね返るが、HPは減らない。
            setattr(self.boss, "invincible", False)
            setattr(self.boss, "_stomp_vulnerable", False)
            setattr(self.boss, "stomp_safe_when_invincible", True)
            setattr(self.boss, "jump_contact_damage", False)
        # 移動開始時は、直前の停止/ジャンプ絵が残らないよう明示的に巡回絵へ戻す。
        setattr(self.boss, "anim_state", "walk")
        setattr(self.boss, "_ground_rush_draw", False)

    def _on_move_stop(self):
        if hasattr(self.boss, "vx"):
            self.boss.vx = 0.0
        if getattr(self.boss, "shield_only_stop", False):
            setattr(self.boss, "invincible", False)
            setattr(self.boss, "_stomp_vulnerable", True)
            setattr(self.boss, "jump_contact_damage", False)
            setattr(self.boss, "stomp_safe_when_invincible", True)
        # animation hint（停止絵を確実にする）
        setattr(self.boss, "anim_state", "stop")

    def _on_ground_rush(self, speed: float, rush_frames: int, land_stop: int):
        if getattr(self.game, "player", None) is None:
            return
        pcx = float(self.game.player.x) + float(getattr(self.game.player, "w", 16)) / 2
        bcx = float(self.boss.x) + float(getattr(self.boss, "w", 64)) / 2
        dir = 1 if pcx >= bcx else -1
        if hasattr(self.boss, "vx"):
            self.boss.vx = dir * abs(float(speed))
        if getattr(self.boss, "shield_only_stop", False):
            if self._preset_name == "stage8_boss":
                # Stage8 boss:
                # 突進は「攻撃後/行動中でも踏めるスキ」として扱う。
                # ここで invincible=True / _stomp_vulnerable=False にすると、
                # 突進開始直後の1発目だけ踏みダメージが通らない。
                setattr(self.boss, "invincible", False)
                setattr(self.boss, "_stomp_vulnerable", True)
                setattr(self.boss, "stomp_safe_when_invincible", True)
                setattr(self.boss, "jump_contact_damage", False)
            else:
                setattr(self.boss, "invincible", True)
                setattr(self.boss, "_stomp_vulnerable", False)
                setattr(self.boss, "stomp_safe_when_invincible", True)
                setattr(self.boss, "jump_contact_damage", False)
        self.boss.face = dir
        self._ground_rush_timer = max(1, int(rush_frames))
        self._ground_rush_land_stop = max(0, int(land_stop))
        setattr(self.boss, "_ground_rush_draw", True)
        setattr(self.boss, "anim_state", "charge")
        play_boss_rush_sfx_at(self.boss)

    def _stage7_edge_x(self, side: str) -> float:
        """Stage7 boss: boss-room edge X in world coordinates.

        Stage9フィールド配置版では MARK_L/R で指定した左右範囲を使う。
        """
        left = float(getattr(self.boss, "field_boss_left", getattr(self.game, "boss_left", 0.0)))
        right = float(getattr(self.boss, "field_boss_right", getattr(self.game, "boss_right", left + globals().get("SCREEN_W", 256))))
        bw = float(getattr(self.boss, "w", 64))
        if str(side) == "right":
            return max(left, right - bw)
        return left

    def _stage7_floor_y(self) -> float:
        floor_y = float(getattr(self.boss, "field_boss_ground_y", globals().get("FLOOR_Y", 208)))
        bh = float(getattr(self.boss, "h", 64))
        return floor_y - bh

    def _stage7_position_x(self, pos: str) -> float:
        """Stage7 boss: left / center / right の待機X座標。"""
        pos = str(pos or "left")
        if pos in ("left", "right"):
            return self._stage7_edge_x(pos)
        left = float(getattr(self.boss, "field_boss_left", getattr(self.game, "boss_left", 0.0)))
        right = float(getattr(self.boss, "field_boss_right", getattr(self.game, "boss_right", left + globals().get("SCREEN_W", 256))))
        bw = float(getattr(self.boss, "w", 64))
        return max(left, min(right - bw, left + (right - left - bw) * 0.5))

    def _stage7_place_at_current_edge(self):
        # 既存名は維持。Stage7専用で、現在位置(left/center/right)へ固定する。
        pos = getattr(self, "_stage7_position", getattr(self, "_stage7_side", "left"))
        self.boss.x = self._stage7_position_x(pos)
        self.boss.y = self._stage7_floor_y()
        self.boss.vx = 0.0
        self.boss.vy = 0.0
        self.boss.face = 1 if pos == "left" else -1
        setattr(self.boss, "anim_state", "stop")
        setattr(self.boss, "invincible", False)
        setattr(self.boss, "_stomp_vulnerable", True)
        setattr(self.boss, "jump_contact_damage", False)

    def _on_stage7_edge_jump_start(self, args: Dict[str, Any]):
        """Stage7: 反対端ジャンプ、または既存ワープ敵風の予告点滅→ワープ。"""
        if self._preset_name != "stage7_boss":
            return
        self._stage7_place_at_current_edge()
        self._stage7_jump_active = False
        self._stage7_warp_active = False
        setattr(self.boss, "_final_phase_blink_timer", 0)

        # 0: 従来ジャンプ / 1: 中央ワープ / 2: 反対端ワープ / 3: 位置変わらずワープ
        choice = randint(0, 3) if bool(args.get("random_warp", False)) else 0

        if choice == 0:
            target_side = "right" if self._stage7_side == "left" else "left"
            self._stage7_jump_active = True
            self._stage7_jump_elapsed = 0
            self._stage7_jump_frames = max(12, int(args.get("frames", 54)))
            self._stage7_jump_arc = float(args.get("arc", 72.0))
            self._stage7_jump_start_x = float(self.boss.x)
            self._stage7_jump_start_y = float(self.boss.y)
            self._stage7_jump_target_x = self._stage7_position_x(target_side)
            self._stage7_jump_target_y = self._stage7_floor_y()
            self._stage7_jump_target_side = target_side
            self.boss.face = 1 if target_side == "right" else -1
            self.boss.vx = 0.0
            self.boss.vy = 0.0
            setattr(self.boss, "anim_state", "jump")
            setattr(self.boss, "invincible", True)
            setattr(self.boss, "_stomp_vulnerable", False)
            setattr(self.boss, "jump_contact_damage", True)
            # Stage7ボスは通常のJumpTowardPlayerではなく、この専用の
            # 反対端ジャンプ処理を使うため、実際のジャンプ開始地点で再生する。
            play_sfx_at_ch(2, "STAGE7_FLOAT_JUMP",
                           self.boss.x, self.boss.y, self.boss.w, self.boss.h,
                           margin=32)
            return

        current_pos = getattr(self, "_stage7_position", getattr(self, "_stage7_side", "left"))
        if choice == 1:
            target_pos = "center"
        elif choice == 2:
            target_pos = "right" if self._stage7_side == "left" else "left"
        else:
            target_pos = current_pos

        self._stage7_warp_active = True
        self._stage7_warp_elapsed = 0
        self._stage7_warp_warn_frames = max(12, int(args.get("warp_warn", args.get("frames", 54))))
        self._stage7_warp_target_pos = target_pos
        self._stage7_warp_target_x = self._stage7_position_x(target_pos)
        self._stage7_warp_target_y = self._stage7_floor_y()
        self.boss.vx = 0.0
        self.boss.vy = 0.0
        setattr(self.boss, "anim_state", "stop")
        setattr(self.boss, "invincible", True)
        setattr(self.boss, "_stomp_vulnerable", False)
        setattr(self.boss, "jump_contact_damage", False)
        setattr(self.boss, "_final_phase_blink_timer", self._stage7_warp_warn_frames)

    def _on_stage7_edge_jump_tick(self):
        if self._preset_name != "stage7_boss":
            return

        if getattr(self, "_stage7_warp_active", False):
            self._stage7_warp_elapsed += 1
            remain = max(0, int(self._stage7_warp_warn_frames) - int(self._stage7_warp_elapsed))
            setattr(self.boss, "_final_phase_blink_timer", remain)
            self.boss.vx = 0.0
            self.boss.vy = 0.0
            setattr(self.boss, "anim_state", "stop")
            if self._stage7_warp_elapsed >= self._stage7_warp_warn_frames:
                old_x, old_y = float(self.boss.x), float(self.boss.y)
                self.boss.x = self._stage7_warp_target_x
                self.boss.y = self._stage7_warp_target_y
                self.boss.vx = 0.0
                self.boss.vy = 0.0
                self._stage7_position = self._stage7_warp_target_pos
                if self._stage7_position in ("left", "right"):
                    self._stage7_side = self._stage7_position
                self.boss.face = 1 if self._stage7_position == "left" else -1
                if (is_rect_on_screen(old_x, old_y, self.boss.w, self.boss.h, margin=16) or
                        is_rect_on_screen(self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=16)):
                    play_sfx("WARP")
                self._stage7_warp_active = False
                setattr(self.boss, "_final_phase_blink_timer", 0)
                setattr(self.boss, "invincible", False)
                setattr(self.boss, "_stomp_vulnerable", True)
                setattr(self.boss, "jump_contact_damage", False)
                if getattr(self.fsm, "_phase", "") == "act":
                    self.fsm.timer = min(getattr(self.fsm, "timer", 0), 1)
            return

        if not getattr(self, "_stage7_jump_active", False):
            return
        self._stage7_jump_elapsed += 1
        t = min(1.0, float(self._stage7_jump_elapsed) / float(max(1, self._stage7_jump_frames)))
        s = t * t * (3.0 - 2.0 * t)
        self.boss.x = self._stage7_jump_start_x + (self._stage7_jump_target_x - self._stage7_jump_start_x) * s
        self.boss.y = self._stage7_jump_start_y + (self._stage7_jump_target_y - self._stage7_jump_start_y) * s - math.sin(math.pi * t) * self._stage7_jump_arc
        self.boss.vx = 0.0
        self.boss.vy = 0.0
        setattr(self.boss, "anim_state", "jump")

        if t >= 1.0:
            self.boss.x = self._stage7_jump_target_x
            self.boss.y = self._stage7_jump_target_y
            self.boss.vx = 0.0
            self.boss.vy = 0.0
            self._stage7_side = self._stage7_jump_target_side
            self._stage7_position = self._stage7_jump_target_side
            self._stage7_jump_active = False
            setattr(self.boss, "anim_state", "stop")
            setattr(self.boss, "_final_phase_blink_timer", 0)
            if getattr(self.fsm, "_phase", "") == "act":
                self.fsm.timer = min(getattr(self.fsm, "timer", 0), 1)

    def _on_random_action(self, args: Dict[str, Any]):
        choices = args.get("choices", ["fan5", "jump", "hyper3", "rush"])
        if not isinstance(choices, (list, tuple)) or not choices:
            choices = ["fan5", "jump", "hyper3", "rush"]

        # Stage8専用:
        # 「ジャンプ → 停止 → ジャンプ」を確実に防ぐ。
        # 直前記録だけだと、ジャンプ内部FSM・停止Wait・RandomActionのタイミング差で
        # まれに候補復帰するため、ジャンプを選んだ瞬間に
        # “次のランダム行動は必ず非ジャンプ” フラグを立てる。
        choices_list = list(choices)
        force_non_jump = (
            self._preset_name in ("stage8_boss", "final_boss")
            and bool(getattr(self, "_stage8_force_next_non_jump", False))
        )
        if force_non_jump:
            filtered = [c for c in choices_list if c != "jump"]
            if filtered:
                choices_list = filtered

        choice = random.choice(choices_list)
        if (
            self._preset_name in ("stage8_boss", "final_boss")
            and bool(getattr(self, "_stage8_force_next_non_jump", False))
            and choice == "jump"
        ):
            # 念のための最終保険。候補リスト異常時でもジャンプ連続を絶対に避ける。
            non_jump_choices = [c for c in choices_list if c != "jump"] or ["fan5"]
            choice = random.choice(non_jump_choices)
        mul = float(args.get("speed_mul", 1.0))

        if bool(args.get("stage6_jump_chain", False)):
            # Stage6専用：小ジャンプを 1回/2回/3回 でランダム実行。
            # 確率は 1回=50%, 2回=30%, 3回=20%。
            r = random.random()
            count = 1 if r < 0.50 else (2 if r < 0.80 else 3)
            self._start_stage6_small_jump_chain(count)
            return

        if choice == "jump":
            # Stage8: ジャンプ後は必ず1.5秒停止。
            # 30fps想定なので 90f = 1.5秒。
            if self._preset_name in ("stage8_boss", "final_boss"):
                self._stage8_force_next_non_jump = True
            if self._preset_name == "final_boss":
                # ラスボス最終フェーズ: ジャンプ直後の停止は0.8秒（60fps想定で48f）
                land_stop = 48
                self._on_jump_toward(5, 2.20 * mul, 2.05 * mul, land_stop)
            else:
                land_stop = 90 if self._preset_name == "stage8_boss" else 8
                self._on_jump_toward(6, 2.05 * mul, 1.90 * mul, land_stop)
        elif choice == "hyper3":
            # 強めのハイパーショット。ラスボス最終フェーズだけ5連射化。
            old_index = getattr(self.fsm, "index", 0)
            self._on_move_stop()
            bx = float(self.boss.x) + float(getattr(self.boss, "w", 64)) / 2
            by = float(self.boss.y) + float(getattr(self.boss, "h", 64)) / 2
            px = float(self.game.player.x) + float(getattr(self.game.player, "w", 16)) / 2
            py = float(self.game.player.y) + float(getattr(self.game.player, "h", 16)) / 2
            base_ang = math.atan2(py - by, px - bx)
            deg_list = (-20, -10, 0, 10, 20) if self._preset_name == "final_boss" else (-14, 0, 14)
            shot_speed = 4.10 if self._preset_name == "final_boss" else 3.65
            for deg in deg_list:
                rad = base_ang + math.radians(deg + random.uniform(-4.0, 4.0))
                shot = Bullet(bx - 5, by - 5, shot_speed * mul * math.cos(rad), power=2, vy=shot_speed * mul * math.sin(rad))
                shot.kind = "power"
                shot.tag = "boss"
                shot.w = 10
                shot.h = 10
                shot.max_range = 460
                self.game.enemy_bullets.append(shot)
            play_sfx_at("CHARGE_SHOT", bx, by, 16, 16, margin=24)
        elif choice == "rush":
            self._on_ground_rush(4.45 * mul, 42, 6)
        else:
            # fan5。ラスボス最終フェーズだけ扇ショット3連射。
            self._on_move_stop()
            saved = getattr(self.fsm, "index", 0)
            if self._preset_name == "final_boss":
                for _ in range(3):
                    self._final_fan_to_player(ways=7, spread=52.0, speed=3.20, jitter=6.0)
            else:
                self._on_fanshot(5, 44.0)

        if self._preset_name in ("stage8_boss", "final_boss"):
            self._stage8_last_random_choice = choice
            # ジャンプ後の次行動で非ジャンプを1回出したら、禁止フラグを解除する。
            # ここで解除するので、ジャンプ直後のWait中に状態がズレても安全。
            if choice != "jump":
                self._stage8_force_next_non_jump = False

    def _final_hp_ratio(self) -> float:
        max_hp = float(getattr(self.boss, "max_hp", getattr(self.boss, "hp", 1)) or 1)
        hp = float(getattr(self.boss, "hp", max_hp))
        return max(0.0, min(1.0, hp / max_hp))

    def _final_phase_from_hp(self) -> int:
        r = self._final_hp_ratio()
        if r > 0.70:
            return 1
        if r > 0.40:
            return 2
        if r > 0.15:
            return 3
        return 4

    def _final_place_right_edge_safe(self):
        """Place final boss at the boss-room right edge, away from player start."""
        left = float(getattr(self.game, "boss_left", 0.0))
        right = float(getattr(self.game, "boss_right", left + globals().get("SCREEN_W", 256)))
        bw = float(getattr(self.boss, "w", 64))
        bh = float(getattr(self.boss, "h", 64))
        self.boss.x = max(left, right - bw)
        self.boss.y = float(globals().get("FLOOR_Y", 208)) - bh
        self.boss.vx = 0.0
        self.boss.vy = 0.0
        self.boss.face = -1
        setattr(self.boss, "anim_state", "stop")

    def _final_reset_action(self, phase: int):
        self._final_phase = phase
        self._final_action = "start"
        self._final_timer = 1
        self._final_sub_timer = 0
        self._final_burst_count = 0
        self._final_summon_cd = 60
        self._mode = None
        self._ground_rush_timer = 0
        self._jump_state = None
        self._stage8_force_next_non_jump = False
        if hasattr(self.game, "boss_stop_timer"):
            self.game.boss_stop_timer = 0
        setattr(self.boss, "invincible", False)
        setattr(self.boss, "_stomp_vulnerable", True)
        setattr(self.boss, "shield_only_stop", False)
        setattr(self.boss, "stomp_safe_when_invincible", True)
        setattr(self.boss, "jump_contact_damage", False)

        # Phase3は右端固定スタート。デバッグ直後のプレイヤー重なりミスも防ぐ。
        if int(phase) == 3:
            self._final_place_right_edge_safe()
            self._final_phase3_side = "right"
            self._final_phase3_jump_active = False

    def _final_fan_to_player(self, ways=5, spread=40.0, speed=2.8, jitter=0.0, power=1):
        if getattr(self.game, "player", None) is None:
            return
        bx = float(self.boss.x) + float(getattr(self.boss, "w", 64)) / 2
        by = float(self.boss.y) + float(getattr(self.boss, "h", 64)) / 2
        px = float(self.game.player.x) + float(getattr(self.game.player, "w", 16)) / 2
        py = float(self.game.player.y) + float(getattr(self.game.player, "h", 16)) / 2
        base_ang = math.atan2(py - by, px - bx) + math.radians(random.uniform(-jitter, jitter))
        ways = max(1, int(ways))
        degs = [0.0] if ways == 1 else [(-spread / 2.0) + (spread / float(ways - 1)) * i for i in range(ways)]
        for deg in degs:
            rad = base_ang + math.radians(deg + random.uniform(-jitter, jitter))
            vx = float(speed) * math.cos(rad)
            vy = float(speed) * math.sin(rad)
            if int(power) >= 2:
                shot = Bullet(bx - 5, by - 5, vx, power=2, vy=vy)
                shot.kind = "power"
                shot.tag = "boss"
                shot.w = 10
                shot.h = 10
                shot.max_range = 460
                self.game.enemy_bullets.append(shot)
            elif hasattr(self.game, "spawn_enemy_bullet"):
                self.game.spawn_enemy_bullet(bx, by, vx, vy, tag="boss")
        if int(power) >= 2:
            play_sfx_at("CHARGE_SHOT", bx, by, 16, 16, margin=24)

    def _final_fan_down(self, ways=5, spread=46.0, speed=3.0):
        bx = float(self.boss.x) + float(getattr(self.boss, "w", 64)) / 2
        by = float(self.boss.y) + float(getattr(self.boss, "h", 64)) - 2
        ways = max(1, int(ways))
        degs = [0.0] if ways == 1 else [(-spread / 2.0) + (spread / float(ways - 1)) * i for i in range(ways)]
        base_ang = math.radians(90.0)
        for deg in degs:
            rad = base_ang + math.radians(deg)
            if hasattr(self.game, "spawn_enemy_bullet"):
                self.game.spawn_enemy_bullet(bx, by, float(speed) * math.cos(rad), float(speed) * math.sin(rad), tag="boss")

    def _final_summon_minions(self):
        left = float(getattr(self.game, "boss_left", 0))
        right = float(getattr(self.game, "boss_right", left + globals().get("SCREEN_W", 256)))
        floor_y = int(globals().get("FLOOR_Y", 208))
        # Phase3召喚数を軽量化。
        # 以前は2〜3体だったが、画面内の敵密度が高くなりすぎるため1〜2体にする。
        count = random.randint(1, 2)
        kinds = [Walker, Hopper, Flyer]
        for _ in range(count):
            kind = random.choice(kinds)
            x_min = int(left + 12)
            x_max = int(max(x_min, right - 28))
            sx = random.randint(x_min, x_max)
            if kind is Flyer:
                sy = random.randint(36, 116)
                patrol_left = max(left, sx - 56)
                patrol_right = min(right, sx + 72)
                # Phase3召喚エネミーは通常スピードに戻す。
                spd = random.choice([-1.0, 1.0])
                e = Flyer(sx, sy, patrol_left, patrol_right, spd=spd, active=True)
                e.vx = spd
            else:
                sy = floor_y - 16
                patrol_left = max(left, sx - 64)
                patrol_right = min(right, sx + 80)
                # Phase3召喚エネミーは通常スピードに戻す。
                if kind is Hopper:
                    spd = random.choice([-0.3, 0.3])
                else:
                    spd = random.choice([-1.0, 1.0])
                e = kind(sx, sy, patrol_left, patrol_right, spd=spd)
                e.vx = spd
            self.game.enemies.append(e)

    def _final_set_move(self, speed: float):
        dir = 1 if float(getattr(self.boss, "vx", 1.0)) >= 0 else -1
        self.boss.vx = dir * float(speed)
        setattr(self.boss, "anim_state", "walk")
        setattr(self.boss, "invincible", False)
        setattr(self.boss, "_stomp_vulnerable", True)

    def _final_busy(self) -> bool:
        # Note:
        # Phase3 edge jump is handled inside _update_final_phase3()
        # by _final_phase3_tick_edge_jump().
        #
        # Do NOT include _final_phase3_jump_active here.
        # If it is treated as a global "busy" state, _update_final_phase_boss()
        # returns before _update_final_phase3() runs, so the edge-jump timer never
        # advances. That leaves the final boss frozen in jump/invincible/contact-
        # damage state after the Stage7-style triple fan-shot sequence.
        return (
            bool(getattr(self, "_jump_state", None))
            or int(getattr(self, "_ground_rush_timer", 0)) > 0
            or int(getattr(self.game, "boss_stop_timer", 0)) > 0
        )

    def _update_final_phase_boss(self):
        phase = self._final_phase_from_hp()
        old_phase = int(getattr(self, "_final_phase", 0) or 0)
        if phase != old_phase:
            self._final_reset_action(phase)
            # 初回生成時は即開始。HP低下によるフェーズ切替時だけ、
            # 約0.5秒の点滅インターバルを入れてプレイヤーに備える時間を作る。
            if old_phase != 0:
                self._final_phase_transition_timer = int(getattr(self, "_final_phase_transition_frames", 30))
                setattr(self.boss, "_final_phase_blink_timer", self._final_phase_transition_timer)
                self.boss.vx = 0.0
                self.boss.vy = 0.0

        # フェーズ切替演出中：行動・攻撃を止め、ボスは点滅＆一時無敵。
        if int(getattr(self, "_final_phase_transition_timer", 0)) > 0:
            self._final_phase_transition_timer -= 1
            setattr(self.boss, "_final_phase_blink_timer", self._final_phase_transition_timer)
            self.boss.vx = 0.0
            self.boss.vy = 0.0
            setattr(self.boss, "invincible", True)
            setattr(self.boss, "_stomp_vulnerable", False)
            setattr(self.boss, "stomp_safe_when_invincible", True)
            setattr(self.boss, "jump_contact_damage", False)
            setattr(self.boss, "anim_state", "stop")
            return
        else:
            setattr(self.boss, "_final_phase_blink_timer", 0)

        # 共通: フェーズ専用処理でも、ジャンプ/突進の内部FSMだけは既存処理を使う。
        self._update_final_micro_fsms()
        if self._final_busy():
            if getattr(self, "_final_action", "") == "wait_floor" and getattr(self.game, "boss_stop_timer", 0) > 0:
                self.boss.vx = 0.0
                self.boss.vy = 0.0
                setattr(self.boss, "anim_state", "stop")
            return

        if phase == 1:
            self._update_final_phase1()
        elif phase == 2:
            self._update_final_phase2()
        elif phase == 3:
            self._update_final_phase3()
        else:
            self._update_final_phase4()

    def _update_final_micro_fsms(self):
        # Stage3系の急降下/上昇復帰も、ラスボス専用更新内で動かす。
        if self._mode == "dive":
            # 降下中は FINAL の jump フレーム(192,0)を固定で使う。
            setattr(self.boss, "anim_state", "jump")
            self.boss.x = float(self.boss.x) + float(self._move_vx)
            self.boss.y = float(self.boss.y) + float(self._move_vy)
            if ((self._move_vx >= 0 and self.boss.x >= self._target_x) or (self._move_vx <= 0 and self.boss.x <= self._target_x)) and ((self._move_vy >= 0 and self.boss.y >= self._target_y) or (self._move_vy <= 0 and self.boss.y <= self._target_y)):
                self.boss.x = float(self._target_x)
                self.boss.y = float(self._target_y)
                self._mode = None
        elif self._mode == "return":
            self.boss.y = float(self.boss.y) + float(self._move_vy)
            if (self._move_vy <= 0 and self.boss.y <= self._target_y) or (self._move_vy >= 0 and self.boss.y >= self._target_y):
                self.boss.y = float(self._target_y)
                self._mode = None
                setattr(self.boss, "invincible", False)
                setattr(self.boss, "_stomp_vulnerable", True)

        # ground rush
        if getattr(self, "_ground_rush_timer", 0) > 0:
            self._ground_rush_timer -= 1
            setattr(self.boss, "anim_state", "charge")
            if self._ground_rush_timer <= 0:
                self.boss.vx = 0.0
                self.game.boss_stop_timer = max(getattr(self.game, "boss_stop_timer", 0), int(getattr(self, "_ground_rush_land_stop", 0)))
                setattr(self.boss, "invincible", False)
                setattr(self.boss, "_stomp_vulnerable", True)
                setattr(self.boss, "stomp_safe_when_invincible", True)
                setattr(self.boss, "jump_contact_damage", False)
                setattr(self.boss, "anim_state", "stop")
                setattr(self.boss, "_ground_rush_draw", False)

        # jump toward player
        if getattr(self, "_jump_state", None):
            if self._jump_state == "pre":
                self._jump_pre -= 1
                if self._jump_pre <= 0:
                    self.game.boss_stop_timer = 0
                    pcx = self.game.player.x + getattr(self.game.player, "w", 16) / 2
                    bcx = self.boss.x + getattr(self.boss, "w", 64) / 2
                    dir = 1 if pcx >= bcx else -1
                    base = max(1.0, abs(float(getattr(self.boss, "vx", 1.0))))
                    self.boss.vx = dir * base * self._jump_x_mul
                    self.boss.vy = float(globals().get("JUMP_VY", -9.0)) * self._jump_y_mul
                    setattr(self.boss, "anim_state", "jump")
                    self._jump_state = "air"
            elif self._jump_state == "air":
                setattr(self.boss, "anim_state", "jump")
                self.boss.vy = float(getattr(self.boss, "vy", 0.0)) + float(globals().get("GRAVITY", 0.5))
                self.boss.y = float(self.boss.y) + float(self.boss.vy)
                floor_y = int(globals().get("FLOOR_Y", 208))
                h = int(getattr(self.boss, "h", 64))
                if self.boss.y + h >= floor_y:
                    self.boss.y = floor_y - h
                    self.boss.vy = 0.0
                    self.game.boss_stop_timer = max(getattr(self.game, "boss_stop_timer", 0), int(getattr(self, "_jump_land", 0)))
                    setattr(self.boss, "anim_state", "stop")
                    setattr(self.boss, "invincible", False)
                    setattr(self.boss, "_stomp_vulnerable", True)
                    setattr(self.boss, "jump_contact_damage", False)
                    self._jump_state = "land"
            elif self._jump_state == "land":
                if getattr(self.game, "boss_stop_timer", 0) <= 0:
                    self._jump_state = None

    def _update_final_phase1(self):
        # HP100〜70%: Stage1〜2強化版。左右移動、扇ショット、たまにジャンプ→着地停止。
        self._final_timer -= 1
        if self._final_timer > 0:
            return
        action = getattr(self, "_final_action", "start")
        if action in ("start", "move"):
            self._final_set_move(2.25)
            self._final_timer = random.randint(70, 105)
            self._final_action = "fan"
        elif action == "fan":
            self.boss.vx = 0.0
            setattr(self.boss, "anim_state", "stop")
            self._final_fan_to_player(ways=5, spread=42.0, speed=2.85, jitter=3.0)
            self._final_timer = 22
            self._final_action = "jump" if random.random() < 0.45 else "move"
        elif action == "jump":
            self._on_jump_toward(8, 2.15, 1.85, 48)
            self._final_timer = 70
            self._final_action = "move"
        else:
            self._final_action = "move"
            self._final_timer = 1

    def _update_final_phase2(self):
        # HP70〜40%: Stage3強化版。上空を横移動しながら高度を下げ、真下扇→急降下→床停止。
        action = getattr(self, "_final_action", "start")
        floor_y = int(globals().get("FLOOR_Y", 208))
        bh = int(getattr(self.boss, "h", 64))
        if action == "start":
            self.boss.y = 34.0
            self._final_set_move(2.70)
            setattr(self.boss, "invincible", True)
            setattr(self.boss, "_stomp_vulnerable", False)
            self._final_timer = 120
            self._final_sub_timer = 20
            self._final_action = "sky"
            return
        if action == "sky":
            setattr(self.boss, "anim_state", "walk")
            setattr(self.boss, "invincible", True)
            setattr(self.boss, "_stomp_vulnerable", False)
            self.boss.y = min(float(floor_y - bh - 54), float(self.boss.y) + 0.20)
            self._final_sub_timer -= 1
            if self._final_sub_timer <= 0:
                self._final_fan_down(ways=5, spread=48.0, speed=3.15)
                self._final_sub_timer = 28
            self._final_timer -= 1
            if self._final_timer <= 0:
                self._on_dive_to_player_floor(7.0, 8)
                self._final_action = "dive"
            return
        if action == "dive":
            if self._mode != "dive":
                self.game.boss_stop_timer = max(getattr(self.game, "boss_stop_timer", 0), 42)
                # 降下完了直後から停止タイマー中も停止絵にする。
                self.boss.vx = 0.0
                self.boss.vy = 0.0
                self.boss.y = floor_y - bh
                setattr(self.boss, "anim_state", "stop")
                self._final_action = "wait_floor"
            return
        if action == "wait_floor":
            self.boss.vx = 0.0
            self.boss.y = floor_y - bh
            setattr(self.boss, "anim_state", "stop")
            if getattr(self.game, "boss_stop_timer", 0) <= 0:
                self._on_return_to_sky(3.6, 34)
                self._final_action = "return"
            return
        if action == "return":
            if self._mode != "return":
                self._final_action = "start"
            return

    def _final_phase3_edge_x(self, side: str) -> float:
        """Phase3: Stage7 boss style edge positions."""
        left = float(getattr(self.game, "boss_left", 0.0))
        right = float(getattr(self.game, "boss_right", left + globals().get("SCREEN_W", 256)))
        bw = float(getattr(self.boss, "w", 64))
        return max(left, right - bw) if str(side) == "right" else left

    def _final_phase3_floor_y(self) -> float:
        return float(globals().get("FLOOR_Y", 208)) - float(getattr(self.boss, "h", 64))

    def _final_phase3_place_edge(self, side: str):
        """Place the final boss on a Stage7-style fixed edge with no horizontal walk."""
        self._final_phase3_side = "right" if str(side) == "right" else "left"
        self.boss.x = self._final_phase3_edge_x(self._final_phase3_side)
        self.boss.y = self._final_phase3_floor_y()
        self.boss.vx = 0.0
        self.boss.vy = 0.0
        self.boss.face = -1 if self._final_phase3_side == "right" else 1
        setattr(self.boss, "anim_state", "stop")
        setattr(self.boss, "invincible", False)
        setattr(self.boss, "_stomp_vulnerable", True)
        setattr(self.boss, "jump_contact_damage", False)

    def _final_phase3_start_edge_jump(self):
        """Phase3: jump from one edge to the other, like Stage7 boss. No lateral walking."""
        side = getattr(self, "_final_phase3_side", "right")
        self._final_phase3_place_edge(side)
        target = "left" if side == "right" else "right"
        self._final_phase3_jump_active = True
        self._final_phase3_jump_elapsed = 0
        # Stage7ボスと同じジャンプ速度・軌道に戻す。
        self._final_phase3_jump_frames = 54
        self._final_phase3_jump_arc = 72.0
        self._final_phase3_jump_start_x = float(self.boss.x)
        self._final_phase3_jump_start_y = float(self.boss.y)
        self._final_phase3_jump_target_x = self._final_phase3_edge_x(target)
        self._final_phase3_jump_target_y = self._final_phase3_floor_y()
        self._final_phase3_jump_target_side = target
        self.boss.face = 1 if target == "right" else -1
        self.boss.vx = 0.0
        self.boss.vy = 0.0
        setattr(self.boss, "anim_state", "jump")
        setattr(self.boss, "invincible", True)
        setattr(self.boss, "_stomp_vulnerable", False)
        setattr(self.boss, "jump_contact_damage", True)

    def _final_phase3_tick_edge_jump(self) -> bool:
        """Return True while the Phase3 edge jump is active."""
        if not getattr(self, "_final_phase3_jump_active", False):
            return False
        self._final_phase3_jump_elapsed += 1
        frames = max(1, int(getattr(self, "_final_phase3_jump_frames", 48)))
        t = min(1.0, float(self._final_phase3_jump_elapsed) / float(frames))
        s = t * t * (3.0 - 2.0 * t)
        self.boss.x = self._final_phase3_jump_start_x + (self._final_phase3_jump_target_x - self._final_phase3_jump_start_x) * s
        self.boss.y = self._final_phase3_jump_start_y + (self._final_phase3_jump_target_y - self._final_phase3_jump_start_y) * s - math.sin(math.pi * t) * self._final_phase3_jump_arc
        self.boss.vx = 0.0
        self.boss.vy = 0.0
        setattr(self.boss, "anim_state", "jump")
        if t >= 1.0:
            self._final_phase3_jump_active = False
            self._final_phase3_side = self._final_phase3_jump_target_side
            self._final_phase3_place_edge(self._final_phase3_side)
            self._final_action = "burst_a1"
            self._final_timer = 24
        return True

    def _update_final_phase3(self):
        # HP40〜110%: Stage4/7複合。
        # 横移動は無し。Stage7ボス風に「端固定→扇ショット3連射→停止→
        # もう一度3連射→停止→反対端へジャンプ」を繰り返す。
        # 召喚とスピードアップ要素は維持。
        self._final_summon_cd -= 1
        if self._final_summon_cd <= 0:
            self._final_summon_minions()
            # 通常より少し早めに召喚して、フェーズ3のスピードアップ感を維持。
            self._final_summon_cd = random.randint(125, 180)

        if self._final_phase3_tick_edge_jump():
            return

        action = getattr(self, "_final_action", "start")
        if action == "start":
            # フェーズ3開始時は必ず右端。デバッグ直開始でもプレイヤーと重ならない。
            self._final_phase3_place_edge("right")
            self._final_timer = 24
            self._final_action = "burst_a1"
            return

        self._final_timer -= 1
        if self._final_timer > 0:
            self.boss.vx = 0.0
            setattr(self.boss, "anim_state", "stop")
            return

        if action in ("burst_a1", "burst_a2", "burst_a3"):
            idx = {"burst_a1": 0, "burst_a2": 1, "burst_a3": 2}[action]
            self._final_phase3_place_edge(getattr(self, "_final_phase3_side", "right"))
            self._final_fan_to_player(
                ways=5,
                spread=42.0 if idx < 2 else 46.0,
                speed=2.70 + idx * 0.10,
                jitter=3.0 if idx < 2 else 4.0,
            )
            self._final_timer = 12 if action != "burst_a3" else 60
            self._final_action = {"burst_a1": "burst_a2", "burst_a2": "burst_a3", "burst_a3": "burst_b1"}[action]
            return

        if action in ("burst_b1", "burst_b2", "burst_b3"):
            idx = {"burst_b1": 0, "burst_b2": 1, "burst_b3": 2}[action]
            self._final_phase3_place_edge(getattr(self, "_final_phase3_side", "right"))
            self._final_fan_to_player(
                ways=5,
                spread=42.0 if idx < 2 else 46.0,
                speed=2.70 + idx * 0.10,
                jitter=3.0 if idx < 2 else 4.0,
            )
            self._final_timer = 12 if action != "burst_b3" else 120
            self._final_action = {"burst_b1": "burst_b2", "burst_b2": "burst_b3", "burst_b3": "edge_jump"}[action]
            return

        if action == "edge_jump":
            self._final_phase3_start_edge_jump()
            return

        self._final_action = "burst_a1"
        self._final_timer = 1

    def _update_final_phase4(self):
        # HP110%以下: Stage8ロジック採用。ただし各攻撃を強化し、速度はStage8の約1割増し。
        if self._final_busy():
            return
        setattr(self.boss, "shield_only_stop", True)
        setattr(self.boss, "stomp_safe_when_invincible", True)
        setattr(self.boss, "invincible", False)
        setattr(self.boss, "_stomp_vulnerable", True)
        self._on_random_action({"choices": ["fan5", "jump", "hyper3", "rush"], "speed_mul": 1.10, "shield_only_stop": True})
        self._final_timer = 1

    def _start_stage6_small_jump_chain(self, count: int):
        """Stage6: 1〜3回の小ジャンプをテンポよく連続実行する。

        2回目・3回目は少しだけ高く、少しだけ遠くへ飛ぶ。
        着地後の予備停止も短くし、各ジャンプ間を詰める。
        """
        count = max(1, min(3, int(count)))
        self._jump_chain_active = True
        self._jump_chain_total = count
        self._jump_chain_done = 0
        self._jump_chain_remaining = count

        # 各ジャンプ間をさらに速くする。2fで「タン、タン、ターン」をより詰める。
        self._jump_chain_pre_stop = 2
        # 小ジャンプ自体も約20%素早くしつつ、1回目 < 2回目 < 3回目で距離と高さを微増。
        self._jump_chain_x_muls = [1.02, 1.10, 1.19]
        self._jump_chain_y_muls = [0.86, 0.94, 1.01]
        self._jump_chain_land_stop = 0

        self._start_next_stage6_chain_jump()

    def _start_next_stage6_chain_jump(self):
        """Stage6 chain jump: remaining回数に応じて次の小ジャンプを開始する。"""
        if not getattr(self, "_jump_chain_active", False):
            return
        if getattr(self, "_jump_chain_remaining", 0) <= 0:
            self._jump_state = None
            self._jump_chain_active = False
            self._jump_chain_remaining = 0
            return

        idx = max(0, min(2, int(getattr(self, "_jump_chain_done", 0))))
        x_mul = self._jump_chain_x_muls[idx]
        y_mul = self._jump_chain_y_muls[idx]

        self._jump_chain_done += 1
        self._jump_chain_remaining -= 1

        self._on_jump_toward(
            self._jump_chain_pre_stop,
            x_mul,
            y_mul,
            self._jump_chain_land_stop,
        )

    def _on_fanshot(self, ways: int, spread: float):
        # 既存の enemy_bullets / Bullet を使った扇状ショット。
        # Stage7 boss はHP半分以下で少しだけ強化し、ラスボス感を出す。
        if getattr(self.game, "player", None) is None:
            return

        args = {}
        try:
            cur = self.fsm.actions[self.fsm.index]
            args = getattr(cur, "args", {}) or {}
        except Exception:
            args = {}

        if self._preset_name == "stage7_boss" and bool(args.get("stage7_edge_lock", False)):
            self._stage7_place_at_current_edge()

        # BossFSMのFanShot共通処理は通常ボス(Game.boss)を参照するため、
        # Stage9フィールド配置の歴代Stage6ボスには防御状態が反映されない。
        # Stage9の再配置個体だけ、通常Stage6と同じく扇ショット中は弱点ではない状態へ戻す。
        if (int(getattr(self.game, "stage", 0)) == 9
                and int(getattr(self.boss, "field_boss_origin_stage", 0) or 0) == 6
                and not bool(getattr(self.boss, "is_midboss", False))):
            setattr(self.boss, "invincible", False)
            setattr(self.boss, "_stomp_vulnerable", False)
            setattr(self.boss, "stomp_safe_when_invincible", True)
            setattr(self.boss, "jump_contact_damage", False)

        ways = int(args.get("ways", ways))
        spread = float(args.get("spread", spread))
        speed = float(args.get("speed", 2.5))
        power = int(args.get("power", 1))

        # Stage7: 後半だけ5方向→7方向へ自然に強化。
        max_hp = float(getattr(self.boss, "max_hp", getattr(self.boss, "hp", 1)) or 1)
        hp = float(getattr(self.boss, "hp", max_hp))
        if self._preset_name == "stage7_boss" and hp <= max_hp * 0.5:
            ways = max(ways, 7)
            spread = max(spread, 48.0)
            speed = max(speed, 2.7)
        if self._preset_name in ("stage8_boss", "final_boss") and hp <= max_hp * 0.35:
            speed += 0.25

        bx = float(self.boss.x) + float(getattr(self.boss, "w", 64)) / 2
        by = float(self.boss.y) + float(getattr(self.boss, "h", 64)) / 2
        px = float(self.game.player.x) + float(getattr(self.game.player, "w", 16)) / 2
        py = float(self.game.player.y) + float(getattr(self.game.player, "h", 16)) / 2
        base_ang = math.atan2(py - by, px - bx)
        angle_jitter = float(args.get("angle_jitter", 0.0))
        if angle_jitter:
            base_ang += math.radians(random.uniform(-angle_jitter, angle_jitter))

        ways = max(1, ways)
        if ways == 1:
            degs = [0.0]
        else:
            start = -spread / 2.0
            step = spread / float(ways - 1)
            degs = [start + step * i for i in range(ways)]

        for deg in degs:
            if angle_jitter:
                deg += random.uniform(-angle_jitter, angle_jitter)
            rad = base_ang + math.radians(deg)
            vx = speed * math.cos(rad)
            vy = speed * math.sin(rad)
            if power >= 2:
                shot = Bullet(bx - 5, by - 5, vx, power=2, vy=vy)
                shot.kind = "power"
                shot.tag = "boss"
                shot.w = 10
                shot.h = 10
                shot.max_range = 420
                self.game.enemy_bullets.append(shot)
            elif hasattr(self.game, "spawn_enemy_bullet"):
                self.game.spawn_enemy_bullet(bx, by, vx, vy, tag="boss")
        if power >= 2:
            play_sfx_at("CHARGE_SHOT", bx, by, 16, 16, margin=24)

    # Stage2 jump helper (pre-stop -> jump -> land-stop)
    def _on_jump_toward(self, pre_stop: int, x_mul: float, y_mul: float, land_stop: int):
        # Stage9に再配置したStage2ボスだけ、前版の小ジャンプを基準に高さを約3倍へ。
        # 高さは初速の2乗に比例するため、初速倍率は sqrt(3) を掛ける。
        # 元のStage2ボス部屋の挙動は変更しない。
        origin_stage = int(getattr(self.boss, "field_boss_origin_stage", 0) or 0)
        self._stage9_stage2_aim_landing = False
        if int(getattr(self.game, "stage", 0)) == 9 and origin_stage == 2:
            pre_stop = min(int(pre_stop), 12)
            x_mul = 1.00
            y_mul = 0.82 * math.sqrt(3.0)
            land_stop = min(int(land_stop), 18)
            self._stage9_stage2_aim_landing = True

        self._jump_pre  = int(pre_stop)
        self._jump_x_mul = float(x_mul)
        self._jump_y_mul = float(y_mul)
        self._jump_land  = int(land_stop)
        self._jump_state = "pre"
        # 停止音を残しつつ、別チャンネルで派手な大ジャンプ音を重ねる。
        # Stage6 boss だけは発射瞬間に専用ロケット音を鳴らすため、
        # ここでは共通の BOSS_BIG_JUMP を鳴らさない。
        play_sfx_at_ch(2, "BOSS_LAND", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
        if self._preset_name not in ("stage6_boss", "stage7_boss", "stage2_boss"):
            play_sfx_at_ch(3, "BOSS_BIG_JUMP", self.boss.x, self.boss.y, self.boss.w, self.boss.h, margin=24)
        setattr(self.boss, "anim_state", "jump")
        self._jump_contact_damage = False
        try:
            cur = self.fsm.actions[self.fsm.index]
            args = getattr(cur, "args", {}) or {}
            self._jump_contact_damage = bool(args.get("jump_contact_damage", False))
        except Exception:
            self._jump_contact_damage = False
        # 小ジャンプ前の予備停止は「弱点の停止」ではなく、ジャンプ準備モーション。
        # shield_only_stop ボスでは、明示的な Wait 停止中だけを弱点にする。
        if getattr(self.boss, "shield_only_stop", False):
            # 小ジャンプ前の予備停止は弱点ではないが、まだジャンプ中でもない。
            # ここも invincible=True にしないことで「踏むと必ずミス」を避ける。
            setattr(self.boss, "invincible", False)
            setattr(self.boss, "_stomp_vulnerable", False)
            setattr(self.boss, "stomp_safe_when_invincible", True)
            setattr(self.boss, "jump_contact_damage", False)
        if hasattr(self.game, "boss_stop_timer"):
            self.game.boss_stop_timer = max(getattr(self.game, "boss_stop_timer", 0), self._jump_pre)
        # Stage2 boss only: pre-jump frames must look like a real stop.
        # Without this, _on_jump_toward() immediately set the jump sprite,
        # making the sequence appear as patrol -> sudden jump.
        if getattr(self, "_preset_name", "") == "stage2_boss":
            if hasattr(self.boss, "vx"):
                self.boss.vx = 0.0
            if hasattr(self.boss, "vy"):
                self.boss.vy = 0.0
            setattr(self.boss, "anim_state", "stop")

class Game:
    CONTINUE_COST = 10000
    STAGE9_UNLOCK_SCORE = 100000
    STEP_BREAK_DELAY_FRAMES = 30 # crash踏んでから壊れる時間

    # ===== 演出時間（60fps想定） =====
    PLAYER_MISS_FRAMES = 72        # 通常/ATTACK中のミス表示：約1.2秒
    PLAYER_RESTART_NOTICE_FRAMES = 24  # ミス演出の最後に RETRY 表示：約0.4秒
    ARMOR_BREAK_FRAMES = 120       # ARMOR被弾後の点滅：約2秒
    BOSS_DEFEAT_FRAMES = 90        # 中ボス/ボス撃破の消滅：約1.5秒

    _instance = None

    @staticmethod
    def _is_power_bullet(b):
        k = getattr(b, "kind", None)
        if k == "power":
            return True
        return getattr(b, "power", 0) >= 2
    def _resolve_bullet_vs_bullet(self, eb):
        for pb in self.bullets:
          if not pb.alive or not eb.alive:
            continue

          # --- すり抜け防止: 判定枠拡大 + 行一致近似（高速弾 & 高さズレ対策） ---
          hit = False
          # 1) 拡大AABB（±2 → ±3 の二重チェック）
          for expand in (2, 4):
            if aabb(pb.x - expand, pb.y - expand, pb.w + expand * 2, pb.h + expand * 2,
                    eb.x - expand, eb.y - expand, eb.w + expand * 2, eb.h + expand * 2):
              hit = True
              break

          # 2) 行一致近似：横レンジが重なり、縦中心差が 6px 以内ならヒット扱い
          if not hit:
            pb_cy = pb.y + pb.h * 0.5
            eb_cy = eb.y + eb.h * 0.5
            horiz_overlap = (pb.x <= eb.x + eb.w) and (eb.x <= pb.x + pb.w)
            dy_close = abs(pb_cy - eb_cy) <= 8
            if horiz_overlap and dy_close:
              hit = True

          if not hit:
            continue

          pb_power = self._is_power_bullet(pb)
          eb_power = self._is_power_bullet(eb)

          if not pb_power and not eb_power:
            # 通常×通常 → 相殺
            pb.alive = False
            eb.alive = False
          elif pb_power and not eb_power:
            # パワー×通常 → パワー貫通（敵弾のみ消滅）
            eb.alive = False
          elif not pb_power and eb_power:
            # 通常×パワー → 通常のみ消滅
            pb.alive = False
          else:
            # パワー×パワー → 相殺
            pb.alive = False
            eb.alive = False

          if getattr(eb, "tag", None) == "stage3_boss_explosive":
            # Stage3ボスショット限定：プレイヤーショットに接触したら
            # 消すだけでなく、既存ミサイル爆発へ移行する。
            pb.alive = False
            eb.trigger_missile_explosion()
          elif not eb.alive:
            break

          if getattr(eb, "tag", None) == "stage3_boss_explosive":
            break

    def __init__(self):
        Game._instance = self
        pyxel.init(SCREEN_W, SCREEN_H, title="Pyxel Multi-Stage")
        self.current_resource_file = None
        self.load_editor_resource(RESOURCE_MAIN)
        self._capture_final_sprite_sheet_cache()
        self.load_editor_resource(RESOURCE_MAIN)
        setup_game_sounds()
        self.music_manager = MusicManager(pyxel)
        self.music_manager.load_all()
        self.scene = "TITLE"
        self.stage = 0
        self.max_stage = 9
        self.hidden_unlocked = False
        # 一度ステージ9へ到達したら、コンテニューでスコアが10万点未満になっても進入権を保持する。
        self.stage9_reached = False
        # ===== DEV: stage/boss selector on TITLE =====
        # 起動時は必ず通常モード。タイトル画面でキーボードは P+Z、ゲームパッドは START+X で切替。
        self.dev_mode = False
        # デバッグメニューは全項目カーソル選択式（上下で項目、左右で値、RETURNで実行）。
        self.dev_menu_index = 0
        self.dev_stage_select = 1
        self.dev_boss_stage_select = 1
        # Stage9 final boss phase test selector
        # 1: 100%-70%, 2: 70%-40%, 3: 40%-110%, 4: 110%以下
        self.dev_final_phase_select = 1
        self.dev_start_time_index = 0
        self.dev_environment_index = 0
        self.dev_final_phase_test_active = False
        self.lives = 5
        self.time_limit = 300 * 60
        # デバッグの「時間制限なし」専用。通常プレイでは常にFalse。
        self.time_limit_disabled = False
        self.score = 0
        self.next_extend = 10000
        # 得点取得済み個体だけを記録する。敵の再配置・再出現機能そのものは変更しない。
        self.scored_enemy_keys = set()
        self.scored_boss_keys = set()
        # Stage9 gem route state. These survive miss-retry and CONTINUE.
        self.stage9_gem_count = 0
        self.stage9_gem_dropped_keys = set()
        self.stage9_pending_gems = {}  # gem_id -> (x, y) for uncollected gems
        self.stage9_gems = []
        self.stage9_midboss_cleared = False
        self.stage9_midboss_cleared_key = None
        self.stage9_door_tiles = set()
        self.stage9_hint_timer = 0
        # Stage9 dedicated midboss lock/unlock presentation state.
        # This persists across miss retry / CONTINUE because Game itself is not recreated.
        self.stage9_midboss_unlock_effect_done = False
        self.stage9_midboss_unlock_timer = 0
        self.stage_miss_counts = {}
        self.clear_bonus_applied_stage = None
        self.clear_bonus_rank = ""
        self.clear_bonus_base = 0
        self.clear_bonus_time = 0
        self.clear_bonus_total = 0
        self.final_life_bonus = 0
        self.cam_x = 0
        self.cam_y = 0
        self.field_bosses = []
        self._field_boss_ais = []
        self.field_midbosses = []
        self._field_midboss_ais = []

        # ===== Damage / defeat effect state =====
        self.player_miss_timer = 0
        self.player_miss_kind = "normal"
        self.player_miss_was_boss = False
        self.armor_break_timer = 0
        self.armor_break_spr = "PLAYER_ARMOR1"
        self.screen_notice_text = ""
        self.screen_notice_timer = 0
        self.boss_defeat_timer = 0
        self.defeated_boss = None
        self.defeated_boss_was_stage_boss = False
        self._ghost_visible_prev = None

        # Stage4中ボス用：床接触による自爆エフェクト（撃破扱いにしない）
        self.midboss_explosion_timer = 0
        self.midboss_explosion_x = 0
        self.midboss_explosion_y = 0
        self.midboss_explosion_w = 32
        self.midboss_explosion_h = 32
        self.midboss_explosion_frames = 30

        # Stage5ボス被弾時の見た目専用爆発（仕様・ダメージ処理は変更しない）
        # 各要素: [world_x, world_y, remaining_frames]
        self.stage5_boss_hit_effects = []


        # ===== Stage visuals (BG color) =====
        # 0=black, 12=sky-ish; tweak per stage if needed
        self.stage_bg_color_map = {
            1: 5, 2: 9, 3: 12, 4: 0, 5: 0, 6: 3, 7: 13, 8: 0, 9: 1
        }
        self.bg_col = self.stage_bg_color_map.get(self.stage or 1, 12)
        self.cp_active = False
        self.cp_pos = (None, None)
        self.activated_checkpoints = set()
        self.last_failed_stage = None
        # 通常タイトル画面のカーソル: 0=START, 1=CONTINUE
        self.title_menu_index = 0

        self.bullets = []
        self.enemy_bullets = []   # 敵弾(プレイヤーにのみ当たる)
        self.items = []
        self.platforms = []
        self.persist_power = 1
        self.persist_armor = 0
        self.persist_pstate = "NONE"
        self.spring_flash = {}  # (tx,ty)->残フレーム：踏んだ瞬間の押し込み演出
        self.pause = False
        # === Charged shot state ===
        self.charging = False
        self.charge_frames = 0

        self.midboss = None
        self.boss = None
        self.boss_shot_cd = 45
        self.boss_stop_timer = 0  # boss normal-shot cooldown (frames)
        self.reaper = Reaper()
        self._midboss_ai = None
        self._boss_ai = None

        self.boss_left = None
        self.boss_right = None
        self.paused = False
        # 割り当て済みDASH入力の2秒長押しコマンド用。
        # TITLE用とPAUSE用を分離し、シーンをまたいだ誤発動を防ぐ。
        self.title_dash_hold_frames = 0
        self.title_dash_hold_triggered = False
        self.pause_dash_hold_frames = 0
        self.pause_dash_hold_triggered = False
        self.prev_z = False
        self.dev_player_invincible = False
        self.environment = "NONE"
        self.environment_elapsed_frames = 0
        self.environment_next_check = ENV_CHECK_INTERVAL_FRAMES
        self.earthquake_warning_timer = 0
        self.earthquake_pending = False
        # 地震の描画専用タイマー。判定・当たり判定・物理には使わない。
        self.earthquake_visual_timer = 0

        # --- TM1 snapshot for stage reset (breakable blocks restore) ---
        self.tm1_snapshot_by_stage = {}

        self.reset_stage(full_reset=True)
        pyxel.run(self.update, self.draw)

    def environment_x_multiplier(self, dx):
        env = getattr(self, "environment", "NONE")
        if not dx:
            return 1.0
        if env == "HEADWIND":
            return 0.8 if dx > 0 else 1.2
        if env == "TAILWIND":
            return 1.2 if dx > 0 else 0.8
        # 酷暑・火事は方向に関係なく、プレイヤーとエネミー双方を減速。
        if env == "HEAT":
            return 0.95
        if env == "FIRE":
            return 0.90
        # 重力異常はプレイヤー／対象エネミーの専用処理内だけで適用する。
        return 1.0

    def set_environment(self, env, announce=True):
        if env not in ENV_TYPES: env = "NONE"
        if env == "FIRE" and self.stage not in (5, 8): env = "NONE"
        self.environment = env
        self.earthquake_warning_timer = 0; self.earthquake_pending = False
        self.earthquake_visual_timer = 0
        # 雪・酷暑・火事の時間デメリットは、発生時点の残り時間から減算する。
        # 残り90秒未満なら変更せず、減算後に90秒未満になる場合は90秒で止める。
        time_penalty_sec = {"SNOW": 50, "HEAT": 50, "FIRE": 100}.get(env)
        if (not getattr(self, "time_limit_disabled", False)
                and time_penalty_sec is not None
                and self.time_limit >= 90 * 60):
            self.time_limit = max(90 * 60, self.time_limit - time_penalty_sec * 60)
        if env == "EARTHQUAKE":
            self.earthquake_warning_timer = EARTHQUAKE_WARNING_FRAMES
            self.earthquake_pending = True
        # 環境変化は効果・演出のみ。プレイ中の文字通知は表示しない。

    def roll_environment(self):
        # ボス部屋では、自然抽選・デバッグ固定を含め環境変化を発動させない。
        if getattr(self, "in_boss_room", False) or getattr(self, "scene", "") == "BOSS":
            self.set_environment("NONE", announce=False)
            return

        # デバッグで環境を固定している場合は、自然抽選を行わない。
        forced = "NONE"
        if self.dev_mode:
            try:
                forced = ENV_TYPES[int(getattr(self, "dev_environment_index", 0))]
            except Exception:
                forced = "NONE"

            # デバッグの「環境変化なし」は自然抽選へ進ませず、必ずNONEで固定する。
            # 以前はNONEだけ自然抽選へ落ち、Stage1候補が雨のみのため雨になることがあった。
            self.set_environment(forced, announce=False)
            return

        # 第1段階：判定タイミングごとに、環境変化そのものが10%で発生。
        if random.random() >= ENV_TRIGGER_CHANCE:
            self.set_environment("NONE")
            return

        # 第2段階：現在のステージで発生可能な候補から1種類を選択。
        candidates = list(STAGE_ENVIRONMENT_CANDIDATES.get(self.stage, ()))
        if not candidates:
            self.set_environment("NONE")
            return

        selected = "NONE"
        if self.stage in EQUAL_ENVIRONMENT_SELECTION_STAGES:
            # Stage9は地震を含む3候補をすべて同率で抽選する。
            selected = random.choice(candidates)
        elif "EARTHQUAKE" in candidates:
            non_earthquake = [env for env in candidates if env != "EARTHQUAKE"]

            # 通常の対象ステージでは、地震は環境変化発生時の20%。
            if random.random() < EARTHQUAKE_SELECTION_CHANCE:
                selected = "EARTHQUAKE"
            elif non_earthquake:
                # 残り80%は、地震以外の候補で均等抽選。
                selected = random.choice(non_earthquake)
            else:
                selected = "EARTHQUAKE"
        else:
            # 地震がないステージは、登録候補すべてを均等抽選。
            selected = random.choice(candidates)

        self.set_environment(selected)

    def _is_environment_exempt_boss_actor(self, actor):
        """中ボス・ボスは、通常配置・Stage9フィールド配置を問わず環境効果対象外。"""
        if actor is None:
            return False
        if actor is getattr(self, "midboss", None) or actor is getattr(self, "boss", None):
            return True
        if isinstance(actor, Boss):
            return True
        if getattr(actor, "is_midboss", False):
            return True
        # Stage9で通常ステージの中ボス・ボスをフィールド配置した個体。
        if hasattr(actor, "field_boss_stage") or hasattr(actor, "field_boss_origin_stage"):
            return True
        return False

    def _enemy_is_grounded_for_earthquake(self, e):
        if self._is_environment_exempt_boss_actor(e):
            return False
        if not getattr(e, "alive", False) or isinstance(e, Flyer): return False
        if getattr(e, "on_ground", False): return True
        foot_y = int(getattr(e,"y",0)+getattr(e,"h",16)+1)
        tx = int((getattr(e,"x",0)+getattr(e,"w",16)*0.5)//TILE); ty=int(foot_y//TILE)
        return is_solid_for_player(tile_at(self.level,self.TILES_X,self.TILES_Y,tx,ty))

    def _player_is_grounded_for_earthquake(self):
        p = getattr(self, "player", None)
        if p is None or not getattr(p, "alive", False):
            return False
        if getattr(p, "on_ground", False):
            return True
        foot_y = float(p.y + p.h)
        ty = int((foot_y + 1) // TILE)
        tx_l = int((p.x + 1) // TILE)
        tx_r = int((p.x + p.w - 2) // TILE)
        for tx in range(tx_l, tx_r + 1):
            if is_solid_for_player(tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty)):
                if -1 <= ty * TILE - foot_y <= 2:
                    return True
        for plat in getattr(self, "platforms", []):
            if (p.x + p.w > plat.x - 1) and (p.x < plat.x + plat.w + 1) and abs((p.y + p.h) - plat.y) <= 3:
                return True
        return False

    def _execute_earthquake(self):
        # 実際の地震発動に合わせて、描画だけの激しい揺れを開始する。
        self.earthquake_visual_timer = 28
        l,r,t,b=self.cam_x,self.cam_x+SCREEN_W,self.cam_y,self.cam_y+SCREEN_H
        for e in self.enemies:
            if l-getattr(e,"w",16)<=getattr(e,"x",0)<=r and t-getattr(e,"h",16)<=getattr(e,"y",0)<=b and self._enemy_is_grounded_for_earthquake(e):
                e.alive=False
        self.enemies=[e for e in self.enemies if e.alive]
        if self._player_is_grounded_for_earthquake(): self.lose_life()

    def update_environment(self):
        # ボス部屋では環境変化の進行・再抽選・地震発動をすべて停止する。
        if self.scene != "PLAY" or getattr(self, "in_boss_room", False) or self.paused:
            return False
        self.environment_elapsed_frames += 1
        if getattr(self, "earthquake_visual_timer", 0) > 0:
            self.earthquake_visual_timer -= 1
        if self.earthquake_pending:
            self.earthquake_warning_timer -= 1
            if self.earthquake_warning_timer <= 0:
                self.earthquake_pending=False; self._execute_earthquake()
                return getattr(self,"player_miss_timer",0)>0
        if self.environment_elapsed_frames >= self.environment_next_check:
            self.environment_next_check += ENV_CHECK_INTERVAL_FRAMES
            self.roll_environment()
        return False

    def apply_environment_enemy_x(self,e,old_x):
        # 中ボス・ボス（Stage9フィールド配置版を含む）は風・酷暑・火事の速度補正対象外。
        if self._is_environment_exempt_boss_actor(e):
            return
        dx=float(getattr(e,"x",old_x))-float(old_x)
        if dx:
            if getattr(self, "environment", "NONE") == "HIGH_GRAVITY":
                # 高重力の横80%は指定対象のみ。Walker/Hopper/Chaserは各専用update内で適用済み。
                if isinstance(e, Flyer):
                    e.x = old_x + dx * HIGH_GRAVITY_MOVE_MULT
            else:
                e.x=old_x+dx*self.environment_x_multiplier(dx)

    def _apply_editor_resource_refs(self):
        """pyxel.load後、TM0/TM1/TM2がIMAGE0を参照するように揃える。"""
        for i in range(3):
            try:
                tm = pyxel.tilemap(i)
                try:
                    tm.imgsrc = 0
                except AttributeError:
                    tm.refimg = 0
            except Exception:
                pass

    def _capture_final_sprite_sheet_cache(self):
        """sekka3.pyxres の Image1 をメモリへ退避する。

        ラスボス描画時に毎フレーム pyxel.load() しないためのキャッシュ。
        取得できない場合は安全に None のままにする。
        """
        self._final_sprite_sheet_cache = None
        self._final_sprite_sheet_installed_for = None
        try:
            cur = getattr(self, "current_resource_file", None)
            pyxel.load(RESOURCE_FINAL)
            src = pyxel.image(1)
            self._final_sprite_sheet_cache = [
                [src.pget(x, y) for x in range(256)]
                for y in range(256)
            ]
            if cur:
                pyxel.load(cur)
                self.current_resource_file = cur
                self._apply_editor_resource_refs()
                # RESOURCE_FINAL(sekka3.pyxres) を一時ロードすると SOUND も切り替わるため、
                # コード側で作る効果音を現在リソースへ再登録する。
                setup_game_sounds()
        except Exception:
            self._final_sprite_sheet_cache = None
            self._final_sprite_sheet_installed_for = None
            try:
                if getattr(self, "current_resource_file", None):
                    pyxel.load(self.current_resource_file)
                    self._apply_editor_resource_refs()
                    setup_game_sounds()
            except Exception:
                pass

    def _ensure_final_sprite_sheet_installed(self):
        """キャッシュ済みラスボス画像を現在リソースの Image2 に一度だけコピーする。"""
        cache = getattr(self, "_final_sprite_sheet_cache", None)
        if cache is None:
            return False
        cur = getattr(self, "current_resource_file", None)
        if getattr(self, "_final_sprite_sheet_installed_for", None) == cur:
            return True
        try:
            dst = pyxel.image(2)
            for y, row in enumerate(cache):
                for x, col in enumerate(row):
                    dst.pset(x, y, col)
            self._final_sprite_sheet_installed_for = cur
            return True
        except Exception:
            return False

    def load_editor_resource(self, filename):
        """必要なときだけ .pyxres / .pyxres2 を切り替える。"""
        if getattr(self, "current_resource_file", None) == filename:
            return
        pyxel.load(filename)
        self.current_resource_file = filename
        self._final_sprite_sheet_installed_for = None
        self._apply_editor_resource_refs()
        # sekka.pyxres / sekka2.pyxres へ切り替えると SOUND もそのファイル内容に戻る。
        # エディタ非依存版では、切替直後に必ずコード側の効果音を再登録する。
        setup_game_sounds()
        if hasattr(self, "music_manager"):
            self.music_manager.load_all()

    def use_resource_for_context(self, stage=None, boss=False):
        """
        通常ステージ: sekka.pyxres
        ステージ9通常マップ: sekka2.pyxres
        ボス部屋で sekka2.pyxres へ切り替えるのはステージ9のみ
        （ステージ5〜8ボス/中ボスは sekka.pyxres Image2 を使う）
        """
        st = self.stage if stage is None else stage
        use_extra = (st in EXTRA_TILEMAP_STAGES) or (boss and st in EXTRA_BOSS_IMAGE_STAGES)
        self.load_editor_resource(RESOURCE_EXTRA if use_extra else RESOURCE_MAIN)

    def stage9_gem_step1_complete(self):
        return int(getattr(self, "stage9_gem_count", 0)) >= STAGE9_GEM_REQUIRED

    def stage9_midboss_debug_override_active(self):
        """DEV_MENUでStage9中ボスを直接選択した時だけ、ジェム無敵を解除する。"""
        return (
            bool(getattr(self, "dev_mode", False))
            and bool(getattr(self, "dev_midboss_test_active", False))
            and int(getattr(self, "stage", 0)) == 9
        )

    def stage9_midboss_gem_lock_active(self):
        """Stage9専用中ボスのジェム条件による無敵が現在有効か。"""
        return (
            int(getattr(self, "stage", 0)) == 9
            and not self.stage9_gem_step1_complete()
            and not self.stage9_midboss_debug_override_active()
        )

    def stage9_boss_door_unlocked(self):
        return self.stage9_gem_step1_complete() and bool(getattr(self, "stage9_midboss_cleared", False))

    def _restore_stage9_gems_from_pending(self):
        self.stage9_gems = []
        if int(getattr(self, "stage", 0)) != 9:
            return
        for gem_id, pos in dict(getattr(self, "stage9_pending_gems", {})).items():
            try:
                x, y = pos
                self.stage9_gems.append(Stage9Gem(gem_id, x, y))
            except Exception:
                continue

    def _spawn_stage9_gems_for_actor(self, actor):
        """Create a persistent, non-overlapping compact cluster around defeated historical actor."""
        if int(getattr(self, "stage", 0)) != 9 or actor is None:
            return
        key = self._boss_score_key(actor, was_stage_boss=False)
        if key in getattr(self, "stage9_gem_dropped_keys", set()):
            return
        count = stage9_gem_reward_for_actor(actor)
        if count <= 0:
            return
        self.stage9_gem_dropped_keys.add(key)

        cx = float(getattr(actor, "x", 0)) + float(getattr(actor, "w", 32)) * 0.5
        cy = float(getattr(actor, "y", 0)) + float(getattr(actor, "h", 32)) * 0.35
        # Up to 3 columns × 2 rows, 18px pitch: close but never overlapping (16px gems).
        cols = min(3, count)
        rows = (count + cols - 1) // cols
        spacing_x, spacing_y = 18, 18
        offsets = []
        remaining = count
        for row in range(rows):
            row_count = min(cols, remaining)
            start_x = -((row_count - 1) * spacing_x) / 2.0
            for col in range(row_count):
                offsets.append((start_x + col * spacing_x, (row - (rows - 1) / 2.0) * spacing_y))
            remaining -= row_count

        max_x = max(0, self.TILES_X * TILE - 16)
        max_y = max(0, self.TILES_Y * TILE - 16)
        base_id = repr(key)
        for i, (ox, oy) in enumerate(offsets):
            gx = clamp(cx - 8 + ox, 0, max_x)
            gy = clamp(cy - 8 + oy, 8, max_y)
            gem_id = f"{base_id}#{i}"
            self.stage9_pending_gems[gem_id] = (float(gx), float(gy))
            self.stage9_gems.append(Stage9Gem(gem_id, gx, gy))

    def _collect_stage9_gems(self):
        if int(getattr(self, "stage", 0)) != 9 or self.player is None:
            return
        for gem in list(getattr(self, "stage9_gems", [])):
            if not gem.alive:
                continue
            if aabb(self.player.x, self.player.y, self.player.w, self.player.h, gem.x, gem.y, gem.w, gem.h):
                gem.alive = False
                before_count = int(getattr(self, "stage9_gem_count", 0))
                self.stage9_gem_count = before_count + 1
                self.stage9_pending_gems.pop(gem.gem_id, None)
                play_sfx("COIN")
                if before_count < STAGE9_GEM_REQUIRED <= self.stage9_gem_count:
                    self._trigger_stage9_midboss_unlock_effect()
        self.stage9_gems = [g for g in getattr(self, "stage9_gems", []) if g.alive]

    def _apply_stage9_door_gate(self):
        """Stage9 boss door gate: hide/show the complete 32x32 door."""
        if int(getattr(self, "stage", 0)) != 9:
            return

        anchors = list(getattr(self, "_boss_door_anchors", []))
        if anchors:
            self.stage9_door_tiles = set(anchors)
        else:
            anchors = list(getattr(self, "stage9_door_tiles", set()))
            # ミス後の再読み込みでは、すでに非表示化されたTM上から扉を再検出できず、
            # _boss_door_anchors が空になることがある。保存済み座標から復元して、
            # 扉本体とゆらめき描画が同じアンカーを参照できるようにする。
            if anchors:
                self._boss_door_anchors = list(anchors)

        # Step3: only after the dedicated Stage9 midboss is actually defeated.
        unlocked = bool(getattr(self, "stage9_midboss_cleared", False))

        def _set_tm8(tm, x8, y8, u_px, v_px):
            tm.pset(x8, y8, (u_px // 8, v_px // 8))

        def _clear_full_32(tm, tx, ty):
            u_air, v_air = TILES["AIR"]
            base_x8 = tx * 2
            base_y8 = tilemap_stage_index(9) * 32 + ty * 2
            for yy in range(4):
                for xx in range(4):
                    _set_tm8(tm, base_x8 + xx, base_y8 + yy, u_air, v_air)

        def _restore_full_32(tm, tx, ty):
            u0, v0 = TILES["BOSS_DOOR"]
            base_x8 = tx * 2
            base_y8 = tilemap_stage_index(9) * 32 + ty * 2
            for yy in range(4):
                for xx in range(4):
                    _set_tm8(tm, base_x8 + xx, base_y8 + yy,
                             u0 + xx * 8, v0 + yy * 8)

        for anchor_tx, anchor_ty in anchors:
            # 32x32 collision footprint
            for dy in range(2):
                for dx in range(2):
                    tx = anchor_tx + dx
                    ty = anchor_ty + dy
                    if 0 <= tx < self.TILES_X and 0 <= ty < self.TILES_Y:
                        self.level[ty][tx] = TILE_DOOR if unlocked else EMPTY

            if unlocked:
                try:
                    tm1 = pyxel.tilemap(1)
                    try:
                        tm1.imgsrc = 0
                    except AttributeError:
                        tm1.refimg = 0
                    _restore_full_32(tm1, anchor_tx, anchor_ty)
                except Exception:
                    pass
            else:
                # TM0/TM1の両方を32x32全部消し、三日月状の残像を残さない。
                for tm_idx in (0, 1):
                    try:
                        tm = pyxel.tilemap(tm_idx)
                        try:
                            tm.imgsrc = 0
                        except AttributeError:
                            tm.refimg = 0
                        _clear_full_32(tm, anchor_tx, anchor_ty)
                    except Exception:
                        pass

    def _trigger_stage9_midboss_unlock_effect(self):
        """Run once when gem total first reaches the unlock requirement."""
        if int(getattr(self, "stage", 0)) != 9:
            return
        if bool(getattr(self, "stage9_midboss_unlock_effect_done", False)):
            return
        self.stage9_midboss_unlock_effect_done = True
        # About 2 seconds of visual clearing; the SFX itself is deliberately longer.
        self.stage9_midboss_unlock_timer = 120
        # Global SFX: requested to be audible regardless of player/camera position.
        play_sfx("STAGE9_UNLOCK_STATIC")

    def _update_stage9_midboss_unlock_effect(self):
        if int(getattr(self, "stage", 0)) == 9 and getattr(self, "stage9_midboss_unlock_timer", 0) > 0:
            self.stage9_midboss_unlock_timer -= 1

    def _draw_stage9_midboss_lock_mist(self):
        """Rounded black haze over the Stage9 midboss.

        Shape follows a soft oval/capsule instead of a rectangle.
        Gradient is strongest at the very top and fades toward the feet.
        On unlock, the haze clears slowly from the feet upward.
        """
        if int(getattr(self, "stage", 0)) != 9:
            return

        mb = getattr(self, "midboss", None)
        if mb is None or not getattr(mb, "alive", False):
            return

        # DEV_MENUで「MIDBOSS: 9」を直接選んだ時だけ、ジェム不足でも霧を表示しない。
        # 通常プレイやDEV STAGE:9など、未選択のデバッグには一切適用しない。
        if self.stage9_midboss_debug_override_active():
            return

        locked = self.stage9_midboss_gem_lock_active()
        timer = int(getattr(self, "stage9_midboss_unlock_timer", 0))
        if (not locked) and timer <= 0:
            return

        x0 = int(getattr(mb, "x", 0))
        y0 = int(getattr(mb, "y", 0))
        w = max(1, int(getattr(mb, "w", 32)))
        h = max(1, int(getattr(mb, "h", 32)))
        head_y = y0
        foot_y = y0 + h - 1
        cx = x0 + w / 2.0

        # During unlock, remove haze from feet upward.
        if locked:
            shade_bottom = foot_y
        else:
            progress = 1.0 - max(0.0, min(1.0, timer / 120.0))
            shade_bottom = int(foot_y - (h + 1) * progress)

        if shade_bottom < head_y:
            return

        total = max(1, h - 1)
        frame_phase = pyxel.frame_count // 5

        try:
            for yy in range(head_y, shade_bottom + 1):
                depth = (yy - head_y) / total

                # Requested direction: darkest at the top, gradually lighter downward.
                alpha = 0.42 - 0.32 * depth
                alpha = max(0.06, alpha)

                # Rounded silhouette: narrower at top/bottom, wider through the body.
                # A slightly asymmetric wobble keeps it looking like mist, not a mask.
                ny = ((yy - (y0 + h * 0.48)) / max(1.0, h * 0.58))
                half = (w * 0.52) * math.sqrt(max(0.0, 1.0 - min(1.0, ny * ny)))
                half += 2.0 + math.sin((yy + frame_phase) * 0.35) * 1.2

                left = int(cx - half)
                right = int(cx + half)
                if right < left:
                    continue

                pyxel.dither(alpha)
                pyxel.rect(left, yy, right - left + 1, 1, 0)

            # Sparse drifting wisps around the outline so the edge does not read as a box.
            pyxel.dither(0.12)
            span = max(1, shade_bottom - head_y + 1)
            for k in range(7):
                yy = head_y + ((frame_phase * 2 + k * 11) % span)
                depth = (yy - head_y) / total
                ny = ((yy - (y0 + h * 0.48)) / max(1.0, h * 0.58))
                half = (w * 0.52) * math.sqrt(max(0.0, 1.0 - min(1.0, ny * ny))) + 3
                side = -1 if ((frame_phase + k) & 1) == 0 else 1
                xx = int(cx + side * half + math.sin((frame_phase + k) * 0.7) * 2)
                pyxel.pset(xx, yy, 0)
        finally:
            pyxel.dither(1.0)

    def add_score(self, pts):
        # 環境変化中は取得点数を1.2倍（端数切り捨て）。
        # 地震および環境変化なしは通常点数。
        env = getattr(self, "environment", "NONE")
        if env not in ("NONE", "EARTHQUAKE"):
            pts = int(pts * 6 // 5)
        self.score += int(pts)
        while self.score >= self.next_extend:
            self.lives += 1
            self.next_extend += 10000

    def _enemy_score_key(self, enemy):
        key = getattr(enemy, "score_key", None)
        if key is not None:
            return key
        return (int(getattr(self, "stage", 0)), "runtime_enemy", id(enemy))

    def award_enemy_defeat_score(self, enemy):
        """通常敵は撃破時だけ加点。同じ配置個体はリトライ後に再撃破しても加点しない。"""
        if enemy is None:
            return 0
        key = self._enemy_score_key(enemy)
        if key in self.scored_enemy_keys:
            return 0
        self.scored_enemy_keys.add(key)
        # Stage9の通常敵は0点。敵自体の再出現・配置処理には触れない。
        if int(getattr(self, "stage", 0)) == 9:
            return 0
        hp = int(getattr(enemy, "max_hp", getattr(enemy, "score_hp", getattr(enemy, "hp", 1))) or 1)
        pts = 300 if hp >= 3 else 200 if hp == 2 else 100
        self.add_score(pts)
        return pts

    def _boss_score_key(self, boss_obj, was_stage_boss=False):
        explicit = getattr(boss_obj, "score_key", None)
        if explicit is not None:
            return explicit
        if was_stage_boss:
            return (int(getattr(self, "stage", 0)), "stage_boss")
        return (int(getattr(self, "stage", 0)), "midboss")

    def award_boss_defeat_score(self, boss_obj, was_stage_boss=False):
        """中ボス・ボス・ラスボスは撃破時に一度だけ加点する。"""
        if boss_obj is None:
            return 0
        key = self._boss_score_key(boss_obj, was_stage_boss)
        if key in self.scored_boss_keys:
            return 0
        self.scored_boss_keys.add(key)
        if was_stage_boss:
            pts = 10000 if int(getattr(self, "stage", 0)) == 9 else 3000
        elif isinstance(key, tuple) and "field_boss" in key:
            pts = 3000
        else:
            pts = 1500
        self.add_score(pts)
        return pts

    def apply_stage_clear_bonus(self):
        """ステージごとに一度だけ、クリア評価＋残タイム加点を行う。"""
        stage = int(getattr(self, "stage", 0))
        if self.clear_bonus_applied_stage == stage:
            return
        misses = int(self.stage_miss_counts.get(stage, 0))
        if misses == 0:
            rank, base = "PERFECT", 3000
        elif 2 <= misses <= 5:
            rank, base = "GOOD", 1500
        else:
            # 指定上、ミス1回はGOOD対象外のためNORMALとして扱う。
            rank, base = "NORMAL", 500
        time_sec = max(0, int(getattr(self, "time_limit", 0)) // 60)
        time_bonus = time_sec * 5
        # ラスボス撃破後のみ、残ライフ×1,000点を追加する。
        life_bonus = max(0, int(getattr(self, "lives", 0))) * 1000 if stage == 9 else 0
        total = base + time_bonus + life_bonus
        self.clear_bonus_applied_stage = stage
        self.clear_bonus_rank = rank
        self.clear_bonus_base = base
        self.clear_bonus_time = time_bonus
        self.final_life_bonus = life_bonus
        self.clear_bonus_total = total
        self.add_score(total)

    def enter_clear_scene(self):
        # 戦闘用の一時タイマーをCLEAR/次ステージへ持ち越さない。
        self.boss_defeat_timer = 0
        self.defeated_boss = None
        self.defeated_boss_was_stage_boss = False
        self.armor_break_timer = 0
        self._lose_life_lock = False
        if self.player:
            self.player.invincible_timer = 0
        self.stop_scene_music()
        self.clear_music_name = "ending" if int(getattr(self, "stage", 0)) == 9 else "stage_clear"
        self.apply_stage_clear_bonus()
        self.scene = "CLEAR"
        self.sync_persist_from_player()

    def sync_persist_from_player(self):
        self.persist_power = self.player.power
        self.persist_armor = self.player.armor
        self.persist_pstate = getattr(self.player, "pstate", "NONE")

    def spawn_enemy_bullet(self, x, y, vx, vy=0, tag = None):
        b = Bullet(x, y, vx, power=0, vy=vy)
        b.tag = tag
        b.pass_tiles = (self.stage == 1 and tag == "boss")
        if tag == "stage3_boss_explosive":
            # Stage3ボス専用：接触時に既存ミサイル爆発へ移行する敵弾。
            b.explode_frames = 30
        self.enemy_bullets.append(b)
        play_sfx_at("SHOT", x, y, 8, 8, margin=16)

    # === TM1 snapshot helpers (8pxセル基準) =========================
    def _tm1_stage_rect8(self, stage):
        """
        TM1上のステージ領域（8pxセル基準）を返す。
        make_level_with_map() が v8_row = stage_index * 32 を使って読む仕様に合わせる。
        幅: WORLD_W(2048px) / 8 = 256セル
        高さ: 1画面256px / 8 = 32セル
        """
        stage_index = tilemap_stage_index(stage)  # stage9はsekka2.pyxres最上段を使う
        ty0 = stage_index * 32
        w = WORLD_W // 8
        h = 32
        return 0, ty0, w, h  # (tx0, ty0, w, h)

    def ensure_tm1_snapshot(self, stage):
        # 既に保存済みなら何もしない
        if stage in self.tm1_snapshot_by_stage:
            return

        try:
            tm = pyxel.tilemap(1)
            # 環境差異対策（make_level_with_map と同じ系統）
            try:
                tm.imgsrc = 0
            except AttributeError:
                tm.refimg = 0
        except Exception:
            return

        tx0, ty0, w, h = self._tm1_stage_rect8(stage)
        snap = []
        for yy in range(h):
            row = []
            for xx in range(w):
                row.append(tm.pget(tx0 + xx, ty0 + yy))
            snap.append(row)
        self.tm1_snapshot_by_stage[stage] = snap

    def restore_tm1_snapshot(self, stage):
        snap = self.tm1_snapshot_by_stage.get(stage)
        if not snap:
            return

        try:
            tm = pyxel.tilemap(1)
            try:
                tm.imgsrc = 0
            except AttributeError:
                tm.refimg = 0
        except Exception:
            return

        tx0, ty0, w, h = self._tm1_stage_rect8(stage)

        # 念のため、保存した高さ/幅に合わせる（不整合で落ちないように）
        hh = min(h, len(snap))
        for yy in range(hh):
            row = snap[yy]
            ww = min(w, len(row))
            for xx in range(ww):
                u, v = row[xx]
                tm.pset(tx0 + xx, ty0 + yy, (u, v))
    # =================================================================

    def make_level_with_map(self, stage):
        TILES_X = WORLD_W // TILE
        TILES_Y = stage_tiles_y(stage)
        level = [[EMPTY for _ in range(TILES_X)] for _ in range(TILES_Y)]
        # ボス扉は全ステージ共通で32x32扱い。
        # エディタ上のBOSS_DOORマーカーを左上基準として記録する。
        boss_door_anchors = []
        # Stage9 は縦3面分。奈落判定は最下段だけなので、固定FLOOR_Yではなく
        # ステージ全体の高さを基準にした行を使えるようにしておく。
        floor_row = (stage_world_h(stage) - (SCREEN_H - FLOOR_Y)) // TILE

        # Keep a pristine snapshot of TM1 for this stage so a full reset can restore breakable blocks.
        self.ensure_tm1_snapshot(stage)

        # === ANCHOR: IMPORT_FROM_EDITOR (NEW) ===
        # TM0/TM1（エディタ描画）を self.level[][] に反映
        # 8pxセル(2x2)の左上を代表として、16pxタイル単位で判定する
        # editor種別 -> 旧タイルID への対応付け
        KIND_TO_ID = {
            "AIR":       EMPTY,
            "GROUND":    SOLID,      # 地形（床）
            "FLOOR":     TILE_BLOCK, # 乗れるブロック
            "BREAKABLE": TILE_BREAK, # 叩くと壊れる
            "ITEM":      TILE_ITEM,  # アイテムブロック（壊れる）
            "MOVE_H":    TILE_BLOCK, # 可動床は旧判定ではブロック扱い（別の動床は self.platforms が担当）
            "MOVE_V":    TILE_BLOCK,
            "CRASH":     TILE_BLOCK, # 踏むと壊れるブロック
            "AUTO":      TILE_GHOST, # 点滅する消えるブロック（当たり判定も点滅）
            "BOSS_DOOR": TILE_DOOR,  # ボス扉
            "COIN":      TILE_COIN,  # 衝突では固体にしない コイン
            "KILL":      TILE_KILL,  # 踏むとミス
            "SPRING":    TILE_SPRING,# 踏むと強制ジャンプ
            "MIDFLAG":   CHECKPOINT,
            "MIDFLAG2":  CHECKPOINT,
        }

        # このステージのゴースト床一覧（AUTO）を記録しておく
        self.ghost_tiles = []
        self._ghost_visible_prev = None
        self.step_break_tiles = set()
        self.step_break_timers = {} # {(tx, ty): 残りフレーム}
        self.spring_tiles = []   # ★追加：スプリング座標

        stage_index = tilemap_stage_index(stage)
        v8_row = stage_index * 32  # 1画面 = 256px = 8pxタイル×32

        TM_BG = pyxel.tilemap(0)
        try:
            TM_BG.imgsrc = 0
        except AttributeError:
            TM_BG.refimg = 0

        # 可変タイルレイヤ（無ければ None）
        TM_VAR = None
        try:
            TM_VAR = pyxel.tilemap(1)
            try:
                TM_VAR.imgsrc = 0
            except AttributeError:
                TM_VAR.refimg = 0
        except Exception:
            TM_VAR = None

        # ★このステージのTM1初期状態を初回だけ保存（壊したブロック復元用）
        self.ensure_tm1_snapshot(stage)

        for ty in range(TILES_Y):
            for tx in range(TILES_X):
                # まず TM0（背景）を確認
                cell0 = TM_BG.pget(tx*2, v8_row + ty*2)
                u0 = cell0[0] * 8; v0 = cell0[1] * 8
                kind0 = UV_TO_KIND.get(_snap8(u0, v0), "AIR")

                # 次に TM1（可変）を見る
                kind1 = "AIR"
                if TM_VAR is not None:
                    cell1 = TM_VAR.pget(tx*2, v8_row + ty*2)
                    u1 = cell1[0] * 8; v1 = cell1[1] * 8
                    kind1 = UV_TO_KIND.get(_snap8(u1, v1), "AIR")

                    # ★FIX: TM1に残った迷子コイン/迷子スプリング対策
                    # TM1のCOIN/SPRINGがTM0の床/ブロックの上に重なると、
                    # 背景側の床を上書きして不自然な判定・描画になる。
                    # そのため、背景側が固体ならTM1側をAIRに戻して無効化する。
                    if kind1 in ("COIN", "SPRING") and kind0 in (
                        "GROUND", "FLOOR", "BREAKABLE", "ITEM", "MOVE_H", "MOVE_V",
                        "CRASH", "AUTO", "BOSS_DOOR", "KILL", "SPRING"
                    ):
                        u_air, v_air = TILES["AIR"]
                        air_ul = (u_air // 8, v_air // 8)
                        air_ur = ((u_air + 8) // 8, v_air // 8)
                        air_ll = (u_air // 8, (v_air + 8) // 8)
                        air_lr = ((u_air + 8) // 8, (v_air + 8) // 8)
                        x0 = tx * 2
                        y0 = v8_row + ty * 2
                        TM_VAR.pset(x0,     y0,     air_ul)
                        TM_VAR.pset(x0 + 1, y0,     air_ur)
                        TM_VAR.pset(x0,     y0 + 1, air_ll)
                        TM_VAR.pset(x0 + 1, y0 + 1, air_lr)
                        kind1 = "AIR"

                # TM1が空ならTM0を採用。TM1に何かあればTM1を優先。
                kind = kind1 if kind1 != "AIR" else kind0

                tile_id = KIND_TO_ID.get(kind, EMPTY)
                level[ty][tx] = tile_id
                if kind == "BOSS_DOOR":
                    boss_door_anchors.append((tx, ty))

                # AUTO（点滅床）は座標を記録
                if kind == "AUTO":
                    self.ghost_tiles.append((tx, ty))
                # CRASH（踏むと壊れるブロック）は踏み壊し用リストに追加
                if kind == "CRASH":
                    self.step_break_tiles.add((tx, ty))
                # ★SPRING（スプリング）は座標を記録（描画アニメ用）
                if kind == "SPRING":
                    self.spring_tiles.append((tx, ty))
        # === ANCHOR END ===

        # 初期配置としての CRASH / AUTO をステージごとに保存（残機減少で復元用）
        if not hasattr(self, "orig_crash_tiles_by_stage"):
            self.orig_crash_tiles_by_stage = {}
            self.orig_ghost_tiles_by_stage = {}
        if stage not in self.orig_crash_tiles_by_stage:
            self.orig_crash_tiles_by_stage[stage] = set(self.step_break_tiles)
            self.orig_ghost_tiles_by_stage[stage] = list(self.ghost_tiles)


        # 全ステージ共通：ボス扉の接触判定を32x32（16px論理タイル2x2）へ拡張。
        # 見た目が32x32なのに判定だけ16x16だった不一致を解消する。
        self._boss_door_anchors = list(dict.fromkeys(boss_door_anchors))
        for door_tx, door_ty in self._boss_door_anchors:
            for dy in range(2):
                for dx in range(2):
                    tx2 = door_tx + dx
                    ty2 = door_ty + dy
                    if 0 <= tx2 < TILES_X and 0 <= ty2 < TILES_Y:
                        level[ty2][tx2] = TILE_DOOR

        return level, TILES_X, TILES_Y


    # --- TM1 snapshot helpers (8pxセル基準：フルリセット時だけ初期化) ---
    def _stage_tm1_rect(self, stage):
        """
        TM1上のステージ領域（8pxセル基準）
        v8_row = stage_index * 32（= 256px / 8px）に合わせる
        幅: WORLD_W(2048px)/8 = 256セル
        高さ: 256px/8 = 32セル
        """
        stage_index = tilemap_stage_index(stage)
        ty0 = stage_index * 32
        return 0, ty0, (WORLD_W // 8), stage_tilemap_h8(stage)  # (tx0, ty0, w, h)

    def ensure_tm1_snapshot(self, stage):
        if not hasattr(self, "tm1_snapshot_by_stage"):
            self.tm1_snapshot_by_stage = {}
        if stage in self.tm1_snapshot_by_stage:
            return

        try:
            tm = pyxel.tilemap(1)
            try:
                tm.imgsrc = 0
            except AttributeError:
                tm.refimg = 0
        except Exception:
            return

        tx0, ty0, w, h = self._stage_tm1_rect(stage)
        snap = []
        for yy in range(h):
            row = []
            for xx in range(w):
                row.append(tm.pget(tx0 + xx, ty0 + yy))
            snap.append(row)
        self.tm1_snapshot_by_stage[stage] = snap

    def restore_tm1_snapshot(self, stage):
        if not hasattr(self, "tm1_snapshot_by_stage"):
            return
        snap = self.tm1_snapshot_by_stage.get(stage)
        if not snap:
            return

        try:
            tm = pyxel.tilemap(1)
            try:
                tm.imgsrc = 0
            except AttributeError:
                tm.refimg = 0
        except Exception:
            return

        tx0, ty0, w, h = self._stage_tm1_rect(stage)

        hh = min(h, len(snap))
        for yy in range(hh):
            row = snap[yy]
            ww = min(w, len(row))
            for xx in range(ww):
                tm.pset(tx0 + xx, ty0 + yy, row[xx])  # row[xx] は (u,v)


    def top_surface_y(self, x, h):
        tx = int(x // TILE)
        for ty in range(self.TILES_Y):
            if tile_is_ground_for_enemy(self.level, self.TILES_X, self.TILES_Y, tx, ty):
                if ty - 1 >= 0 and not tile_is_ground_for_enemy(self.level, self.TILES_X, self.TILES_Y, tx, ty - 1):
                    return ty * TILE - h
        return FLOOR_Y - h

    def music_name_for_scene(self):
        """現在シーンに対応するBGM名を返す。

        musicフォルダ内に該当曲がまだ無い場合でも、MusicManager側で安全に無音扱いにする。
        BGM追加時は music/stage1.py のように作成し、MUSIC_NAME を "stage1" にする。
        """
        try:
            if self.scene == "TITLE":
                return "title"
            if self.scene == "GAMEOVER":
                return "gameover"
            if self.scene == "CLEAR":
                # CLEAR画面に入った瞬間の曲名を優先する。
                # これにより、通常ステージクリア後にステージ番号が進んでも
                # ending が誤って鳴ることを防ぐ。
                clear_music = getattr(self, "clear_music_name", None)
                if clear_music in ("stage_clear", "ending"):
                    return clear_music
                return "ending" if int(getattr(self, "stage", 0)) == 9 else "stage_clear"
            if self.scene == "PLAY" and int(getattr(self, "stage", 0)) > 0:
                return f"stage{int(self.stage)}"
            if self.scene == "BOSS" and int(getattr(self, "stage", 0)) > 0:
                if int(self.stage)==9:
                    return "final_boss"
                stage_boss_name = f"boss_stage{int(self.stage)}"
                if hasattr(self, "music_manager") and self.music_manager.has(stage_boss_name):
                    return stage_boss_name
                return "boss"
        except Exception:
            pass
        return None

    def stop_scene_music(self):
        """BGMだけ止める。SFX用チャンネルは止めない。"""
        try:
            self.music_manager.stop()
        except Exception:
            pass

    def update_scene_music(self, restart=False):
        """シーン状態に合わせてBGMを安全に開始/停止する。

        基本ルール:
        - ミス演出中はBGM停止
        - ポーズ中はBGM停止
        - リトライ時は restart=True で曲頭から再生
        - 曲ファイルが未作成なら無音のまま続行し、実行エラーにしない
        """
        try:
            if getattr(self, "paused", False):
                self.music_manager.stop()
                return
            if getattr(self, "player_miss_timer", 0) > 0:
                # ミス演出中は通常BGMを止め、専用の短いミス曲だけを鳴らす。
                # player_miss.py が無い環境では MusicManager 側で安全に無音扱い。
                self.music_manager.play("player_miss", restart=False)
                return
            name = self.music_name_for_scene()
            if name is None:
                self.music_manager.stop()
                return
            self.music_manager.play(name, restart=restart)
        except Exception:
            pass


    def reset_stage(self, full_reset=False):
        # 前のボス/中ボス撃破演出タイマーを新しいステージへ持ち越さない。
        # Stage9の歴代フィールドボス撃破後タイマーが、後から生成された
        # 通常中ボス self.midboss を消してしまう不具合もここで防ぐ。
        self.boss_defeat_timer = 0
        self.defeated_boss = None
        self.defeated_boss_was_stage_boss = False

        # ステージ9だけは追加リソース側のタイルマップを読む。
        # 5〜8通常ステージは従来どおり sekka.pyxres を読む。
        self.use_resource_for_context(self.stage, boss=False)

        # refresh BG color for current stage
        self.in_boss_room = False
        if self.clear_bonus_applied_stage != int(getattr(self, "stage", 0)):
            self.clear_bonus_rank = ""
            self.clear_bonus_base = 0
            self.clear_bonus_time = 0
            self.clear_bonus_total = 0
        if full_reset:
            # Full reset (GAME OVER / GAME CLEAR etc.): restore TM1 to the pristine state
            # so breakable blocks/items come back.
            self.restore_tm1_snapshot(self.stage)

        self.level, self.TILES_X, self.TILES_Y = self.make_level_with_map(self.stage)
        globals()["CURRENT_STAGE_WORLD_H"] = self.TILES_Y * TILE
        self.cam_x = 0
        self.cam_y = 0


        # ===== Stage visuals (BG color) =====
        # 動く床
        self.platforms = []

        # ★エディタ（TM1）からスポーン
        try:
            editor_plats = parse_editor_platforms(self.stage, self.TILES_X, self.TILES_Y)
            self.platforms.extend(editor_plats)
        except Exception as _e:
            # TM1 が無い環境などでも壊れないようフェイルセーフ
            pass

        # 敵配置（TM2エディタ配置のみ）
        self.enemies = parse_editor_enemies(
            self.stage,
            self.TILES_X,
            self.TILES_Y,
            self
        )

        door_world_x = (self.TILES_X - 8) * TILE

        mb_def = (STAGE_BOSS_DEF.get(self.stage, {}) or {}).get("mid", DEFAULT_MIDBOSS_DEF)
        self.midboss = Boss(
            door_world_x - 48,
            FLOOR_Y - mb_def["h"],
            hp=mb_def["hp"],
            sprite_key=mb_def["sprite_key"],
            is_midboss=True
        )
        self.midboss.w = mb_def["w"]
        self.midboss.h = mb_def["h"]

        # --- Midboss FSM wiring (same adapter; simple presets) ---
        self._midboss_ai = BossAIAdapter(self, self.midboss)
        preset = mb_def.get("preset")
        if preset:
            self._midboss_ai.load_preset(preset)

        # 通常Stage4中ボスだけ、TM2エディタX=224をプレイヤーが超えるまで
        # 描画・AI更新・接触／弾当たり判定を停止する。Stage9召喚版には適用しない。
        if int(getattr(self, "stage", 0)) == 4:
            self.midboss.stage4_wait_for_tm2_x = 224
            self.midboss.stage4_tm2_x_activated = False

        self.boss = None

        # Stage9通常フィールド内ボス/中ボス準備。
        # コードで座標・範囲を指定する方式は使わず、TM2マーカーだけで配置する。
        # 出現位置: BOSS1_MARK〜BOSS8_MARK / MID1_MARK〜MID8_MARK
        # 左右範囲: 同じ行の MARK_L / MARK_R
        # 上下範囲: 同じ列の MARK_A / MARK_U
        self.field_bosses = []
        self._field_boss_ais = []
        self.field_midbosses = []
        self._field_midboss_ais = []
        if self.stage == 9:
            self.field_bosses, self._field_boss_ais = parse_stage9_field_boss_markers(self)
            self.field_midbosses, self._field_midboss_ais = parse_stage9_field_midboss_markers(self)

            # Stage9専用中ボスも固定座標生成を廃止し、MID9_MARKによるエディタ配置に統一。
            self.midboss, self._midboss_ai = parse_stage9_dedicated_midboss_marker(self)
            # マーカー未配置なら中ボスは存在しない。後から座標を置くだけで生成される。
            if self.midboss is not None:
                current_mid9_key = getattr(self.midboss, "score_key", None)
                cleared_mid9_key = getattr(self, "stage9_midboss_cleared_key", None)
                # 撃破済み判定は配置座標を含む個体キーが一致した時だけ適用。
                # エディタでMID9_MARKを移動・置き直した場合は新しい個体として出現する。
                if (bool(getattr(self, "stage9_midboss_cleared", False))
                        and cleared_mid9_key is not None
                        and current_mid9_key == cleared_mid9_key):
                    self.midboss.alive = False
                elif cleared_mid9_key != current_mid9_key:
                    self.stage9_midboss_cleared = False

        # Stage9 gimmick persistence / gate. full_reset=True is stage start or CONTINUE,
        # while miss retry uses full_reset=False and must not repeat the hint.
        self._restore_stage9_gems_from_pending()
        if self.stage == 9:
            self._apply_stage9_door_gate()
            if full_reset:
                self.stage9_hint_timer = 180
        else:
            self.stage9_hint_timer = 0

        self.reaper = Reaper()

        if full_reset:
            self.cp_active = False
            self.cp_pos = (None, None)
            # 通常プレイはステージ9だけ総時間600秒。その他ステージは従来どおり300秒。
            # ミス後のfull_reset=Falseでは残り時間を引き継ぐため、既存の総時間ルールは維持。
            self.time_limit = (600 if int(getattr(self, "stage", 0)) == 9 else 300) * 60
            self.time_limit_disabled = False

        if self.cp_active and self.cp_pos[0] is not None:
            px, py = self.cp_pos
            self.player = Player(px, py)
        else:
            self.player = Player(10, FLOOR_Y - 16)

        # --- persist から復元（pstate対応） ---
        self.player.power = max(1, self.persist_power)
        self.player.pstate = getattr(self, "persist_pstate", "NONE")

        if self.player.pstate == "ARMOR":
            self.player.armor = max(0, self.persist_armor)
        else:
            # ATTACK / NONE は耐久を持たない
            self.player.armor = 0

        # サイズは pstate で決定（armor依存にしない）
        if self.player.pstate in ("ATTACK", "ARMOR"):
            self.player.set_size_keep_bottom(32, 32)
        else:
            self.player.set_size_keep_bottom(16, 16)

        # 無敵は初期化（安全）
        self.player.invincible_timer = 0

        self.bullets.clear()

        # ...(リセット末尾あたり)
        self.bullets.clear()
        self.enemy_bullets.clear()
        self.items.clear()
        # 9面用：旧・距離トリガー式フィールドボスは廃止。
        # 現在はTM2マーカー配置のみ使用する。
        self.field_boss_queue = []
        self.next_boss_index = 0
        self.next_boss_triggers = []


        dev_time_sec = DEV_START_TIME_SEC
        if self.dev_mode:
            try:
                dev_time_sec = DEV_START_TIME_OPTIONS[int(getattr(self, "dev_start_time_index", 0))]
            except Exception:
                dev_time_sec = DEV_START_TIME_SEC

        # デバッグ選択はステージを問わず適用。時間制限なしでは数値を壊さず、減算だけ停止する。
        if dev_time_sec == DEV_TIME_NO_LIMIT:
            self.time_limit_disabled = True
        elif dev_time_sec is not None:
            self.time_limit_disabled = False
            self.time_limit = int(dev_time_sec) * 60

        self.environment_elapsed_frames = 0
        self.environment_next_check = ENV_CHECK_INTERVAL_FRAMES
        self.environment = "NONE"
        self.earthquake_warning_timer = 0
        self.earthquake_pending = False
        self.roll_environment()

        # ステージ開始/リスタート時は、デバッグ無敵をいったんOFFに戻す。
        self.dev_player_invincible = False

    def goto_title(self):
        self.stop_scene_music()
        self.scene = "TITLE"
        self.stage = 0
        self.lives = 5
        self.score = 0
        self.next_extend = 10000
        self.scored_enemy_keys.clear()
        self.scored_boss_keys.clear()
        self.stage_miss_counts.clear()
        self.clear_bonus_applied_stage = None
        self.clear_bonus_rank = ""
        self.clear_bonus_base = 0
        self.clear_bonus_time = 0
        self.clear_bonus_total = 0
        self.final_life_bonus = 0
        self.stage9_reached = False
        self.cp_active = False
        self.cp_pos = (None, None)
        self.last_failed_stage = None
        self.title_menu_index = 0
        # Controller / virtual-pad CONFIG state.
        self.config_menu_index = 0
        self.config_capture_action = None
        self.hidden_unlocked = False
        self.dev_midboss_test_active = False
        self.dev_final_phase_test_active = False
        self.persist_power = 1
        self.persist_armor = 0
        self.persist_pstate = "NONE"
        # ポーズ中にタイトルへ戻った場合、次回スタート時にポーズ状態を残さない。
        self.paused = False
        self.pause_dash_hold_frames = 0
        self.pause_dash_hold_triggered = False
        self.title_dash_hold_frames = 0
        self.title_dash_hold_triggered = False


    def restore_stepbreak_and_ghost_blocks(self):
        """残機が減ったときに CRASH床とAUTO床だけエディタ状態へ戻す"""
        # ステージ別に保存しておいた初期配置がなければ何もしない
        if not hasattr(self, "orig_crash_tiles_by_stage"):
            return
        stage = self.stage
        crash_map = self.orig_crash_tiles_by_stage.get(stage, None)
        ghost_map = getattr(self, "orig_ghost_tiles_by_stage", {}).get(stage, None) \
            if hasattr(self, "orig_ghost_tiles_by_stage") else None

        # CRASH 床を元に戻す
        if crash_map:
            for (tx, ty) in crash_map:
                try:
                    put_kind(tx, ty, "CRASH")
                except Exception:
                    # タイルマップが存在しない環境でもゲームが落ちないようにフェイルセーフ
                    pass

        # AUTO（点滅する消える床）を元に戻す
        if ghost_map:
            for (tx, ty) in ghost_map:
                try:
                    put_kind(tx, ty, "AUTO")
                except Exception:
                    pass

    def start_player_miss_effect(self, kind="normal"):
        """通常/ATTACK中のミス。演出を表示してから残機-1・リスタートする。"""
        if getattr(self, "player_miss_timer", 0) > 0:
            return

        self.stop_scene_music()
        play_sfx("PLAYER_DAMAGE")
        try:
            # 効果音を先に鳴らし、その直後に短いミス曲を曲頭から再生する。
            self.music_manager.play("player_miss", restart=True)
        except Exception:
            pass
        self.player_miss_kind = kind
        self.player_miss_was_boss = (self.scene == "BOSS")
        st = int(getattr(self, "stage", 0))
        self.stage_miss_counts[st] = int(self.stage_miss_counts.get(st, 0)) + 1
        self.player_miss_timer = self.PLAYER_MISS_FRAMES
        self.screen_notice_text = "MISS"
        self.screen_notice_timer = self.PLAYER_MISS_FRAMES

        # 演出中は動かさない
        if self.player:
            self.player.vx = 0
            self.player.vy = 0
            self.player.alive = True

            # ミス後は通常状態へ戻す（復帰後の見た目を揃える）
            self.player.pstate = "NONE"
            self.player.armor = 0
            self.player.power = 1
            self.player.set_size_keep_bottom(16, 16)

        # 次のリスタートで強化が復元されないよう persist も通常へ戻す
        self.persist_pstate = "NONE"
        self.persist_armor = 0
        self.persist_power = 1

    def finish_player_miss_effect(self):
        """ミス演出終了後に、ここで初めて残機を減らしてリスタートする。"""
        kind = getattr(self, "player_miss_kind", "normal")
        was_boss = getattr(self, "player_miss_was_boss", False)

        self.lives -= 1
        if self.lives <= 0:
            self.stop_scene_music()
            self.scene = "GAMEOVER"
            self.last_failed_stage = self.stage
            self._lose_life_lock = False
            return

        if kind != "void":
            try:
                self.restore_stepbreak_and_ghost_blocks()
            except Exception:
                pass

        if was_boss:
            if getattr(self, "dev_final_phase_test_active", False):
                self.enter_final_boss_phase_test_room(getattr(self, "dev_final_phase_select", 1))
            else:
                self.enter_boss_room()
        elif getattr(self, "dev_midboss_test_active", False):
            # DEV中ボステスト中は、ミス後もステージ先頭ではなく同じ中ボス直前から再開。
            self.enter_midboss_test_room()
        elif self.cp_active and self.cp_pos[0] is not None:
            self.reset_stage(full_reset=False)
        else:
            self.reset_stage(full_reset=False)

        if kind == "timeover" and not was_boss:
            self.time_limit = 90 * 60

        self._lose_life_lock = False
        self.update_scene_music(restart=True)

    def start_armor_break_effect(self):
        """ARMOR中の被弾。残機は減らさず、次の状態の見た目を早点滅表示する。"""
        if getattr(self, "armor_break_timer", 0) > 0:
            return

        play_sfx("ARMOR_BREAK")
        self.armor_break_timer = self.ARMOR_BREAK_FRAMES

        # ARMOR×2 → ARMOR×1
        # 点滅中も最終状態も「アーマー×1」の32x32描画にする。
        if getattr(self.player, "armor", 0) >= 2:
            self.armor_break_spr = "PLAYER_ARMOR1"

            self.player.pstate = "ARMOR"
            self.player.armor = 1
            self.player.power = 1
            self.player.set_size_keep_bottom(32, 32)

            self.persist_pstate = "ARMOR"
            self.persist_armor = 1
            self.persist_power = 1

        # ARMOR×1 → 通常
        # こちらは今まで通り、通常16x16描画の点滅にする。
        else:
            self.armor_break_spr = "PLAYER"

            self.player.pstate = "NONE"
            self.player.armor = 0
            self.player.power = 1
            self.player.set_size_keep_bottom(16, 16)

            self.persist_pstate = "NONE"
            self.persist_armor = 0
            self.persist_power = 1

        self.player.invincible_timer = self.ARMOR_BREAK_FRAMES

        self._lose_life_lock = False

    def start_boss_defeat_effect(self, boss_obj, was_stage_boss=False):
        """中ボス/ボス共通の撃破演出。現在の描画を早点滅させて消す。"""
        if boss_obj is None or getattr(self, "boss_defeat_timer", 0) > 0:
            return

        play_sfx("BOSS_DEFEAT" if was_stage_boss else "MIDBOSS_DEFEAT")
        # Stage9 historical field bosses/midbosses drop gems only once per original actor.
        # Drop state and any uncollected gems persist through miss/CONTINUE.
        if int(getattr(self, "stage", 0)) == 9 and hasattr(boss_obj, "field_boss_origin_stage"):
            self._spawn_stage9_gems_for_actor(boss_obj)
        self.award_boss_defeat_score(boss_obj, was_stage_boss=was_stage_boss)
        # Step2: the dedicated Stage9 midboss can only reach defeat after Step1 is complete.
        dedicated_midboss = getattr(self, "midboss", None)
        if (int(getattr(self, "stage", 0)) == 9
                and dedicated_midboss is not None
                and boss_obj is dedicated_midboss
                and not was_stage_boss):
            self.stage9_midboss_cleared = True
            self.stage9_midboss_cleared_key = getattr(boss_obj, "score_key", None)
            self._apply_stage9_door_gate()
        self.defeated_boss = boss_obj
        self.defeated_boss_was_stage_boss = bool(was_stage_boss)
        self.boss_defeat_timer = self.BOSS_DEFEAT_FRAMES

        # 動きを止める
        boss_obj.alive = False
        boss_obj.vx = 0
        boss_obj.vy = 0
        setattr(boss_obj, "invincible", True)
        setattr(boss_obj, "_stomp_vulnerable", False)

        # 弾やザコが残っていると演出中に事故るので掃除
        self.enemy_bullets.clear()
        self.bullets.clear()
        if was_stage_boss:
            self.enemies.clear()

    def start_midboss_explosion_effect(self, boss_obj, frames=30):
        """Stage4中ボス用：床接触で自爆。通常撃破扱いにはしない。"""
        if boss_obj is None or getattr(self, "midboss_explosion_timer", 0) > 0:
            return

        self.midboss_explosion_x = float(getattr(boss_obj, "x", 0.0))
        self.midboss_explosion_y = float(getattr(boss_obj, "y", 0.0))
        self.midboss_explosion_w = int(getattr(boss_obj, "w", 32))
        self.midboss_explosion_h = int(getattr(boss_obj, "h", 32))
        self.midboss_explosion_frames = max(1, int(frames))
        self.midboss_explosion_timer = self.midboss_explosion_frames
        # 爆発終了時に消す対象を明示的に保持する。
        # Stage9では歴代Stage4中ボスと専用MID9が同時に存在し得るため、
        # self.midbossを無条件で消すと別個体のMID9まで消えてしまう。
        self.midboss_explosion_target = boss_obj

        # 撃破演出ではなく、自爆として消す。
        boss_obj.alive = False
        boss_obj.vx = 0
        boss_obj.vy = 0
        setattr(boss_obj, "invincible", True)
        setattr(boss_obj, "_stomp_vulnerable", False)

    def update_midboss_explosion_effect(self):
        """自爆中の爆風判定。Trueなら通常update継続、ミス時だけFalse。"""
        if getattr(self, "midboss_explosion_timer", 0) <= 0:
            return True

        self.midboss_explosion_timer -= 1

        # ミサイル爆発と同じイメージで、少し広めの爆風判定。
        ex = self.midboss_explosion_x - 12
        ey = self.midboss_explosion_y - 12
        ew = self.midboss_explosion_w + 24
        eh = self.midboss_explosion_h + 24
        if self.player and aabb(self.player.x, self.player.y, self.player.w, self.player.h, ex, ey, ew, eh):
            if self.player.invincible_timer <= 0:
                self.lose_life()
                return False

        if self.midboss_explosion_timer <= 0:
            exploded = getattr(self, "midboss_explosion_target", None)
            # 通常のself.midboss自身が自爆した場合だけ専用参照を解除する。
            # Stage9の歴代フィールド中ボスが自爆した場合は、専用MID9を残す。
            if exploded is not None and exploded is getattr(self, "midboss", None):
                self.midboss = None
                self._midboss_ai = None
            self.midboss_explosion_target = None
        return True

    def update_effect_timers(self):
        """演出中なら True を返し、通常updateを止める。"""
        if getattr(self, "player_miss_timer", 0) > 0:
            self.player_miss_timer -= 1

            # ミス演出の後半で、これから復帰することを画面表示
            if self.player_miss_timer <= self.PLAYER_RESTART_NOTICE_FRAMES:
                self.screen_notice_text = "RETRY"
            else:
                self.screen_notice_text = "MISS"
            self.screen_notice_timer = max(1, self.player_miss_timer)

            if self.player_miss_timer <= 0:
                self.screen_notice_text = ""
                self.screen_notice_timer = 0
                self.finish_player_miss_effect()
            return True

        # ボス撃破演出をARMOR点滅より優先し、未消化タイマーの持越しを防ぐ。
        if getattr(self, "boss_defeat_timer", 0) > 0:
            play_boss_defeat_explosion_sfx_at(getattr(self, "defeated_boss", None))
            self.boss_defeat_timer -= 1
            if self.boss_defeat_timer <= 0:
                defeated = self.defeated_boss
                if self.defeated_boss_was_stage_boss:
                    self.enter_clear_scene()
                else:
                    # Stage9歴代フィールドボス/中ボスも同じ撃破タイマーを使うため、
                    # 「非ステージボスなら常に self.midboss=None」は誤り。
                    # 実際に倒した個体が通常中ボスそのものの場合だけ消す。
                    if defeated is not None and defeated is self.midboss:
                        self.midboss = None
                self.defeated_boss = None
            return True

        if getattr(self, "armor_break_timer", 0) > 0:
            self.armor_break_timer -= 1
            if self.armor_break_timer <= 0:
                self.player.invincible_timer = 0
            return False  # ARMOR点滅中は動ける


        return False

    def lose_life(self, kind="normal"):
        if getattr(self, "_lose_life_lock", False):
            return
        self._lose_life_lock = True

        # 奈落・時間切れ・通常被弾は、演出後に残機-1
        if kind == "void":
            self.start_player_miss_effect(kind="void")
            return

        # ARMOR中の被弾は残機を減らさず、早点滅して通常へ戻す
        if self.player.pstate == "ARMOR":
            self.start_armor_break_effect()
            return

        # ATTACK中/通常の被弾：演出後に残機-1・リスタート
        self.start_player_miss_effect(kind=kind)

    def try_activate_checkpoint(self):
        l, r, t, b = rect_to_tiles(self.player.x, self.player.y, self.player.w, self.player.h)
        for ty in range(t, b + 1):
            for tx in range(l, r + 1):
                if tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty) == CHECKPOINT:
                    if not hasattr(self, "activated_checkpoints"):
                        self.activated_checkpoints = set()
                    cp_key = (int(self.stage), tx, ty)
                    if cp_key not in self.activated_checkpoints:
                        self.activated_checkpoints.add(cp_key)
                        play_sfx_at("CHECKPOINT", tx * TILE, ty * TILE, TILE, TILE)
                    self.cp_active = True
                    self.cp_pos = (tx * TILE, ty * TILE - (self.player.h - 2))
                    return

    def enter_midboss_test_room(self):
        """DEV_MENU専用：選択ステージの中ボスだけをすぐ試す。通常プレイには影響させない。"""
        if not self.dev_mode:
            return

        # ミス後の再チャレンジでも中ボス直前から再開するための目印。
        self.dev_midboss_test_active = True
        self.dev_final_phase_test_active = False
        self.boss_defeat_timer = 0
        self.defeated_boss = None
        # Stage9のDEV MIDは専用中ボスを生存状態から試す。
        if int(getattr(self, "stage", 0)) == 9:
            self.stage9_midboss_cleared = False

        # 通常ステージ開始と同じ初期化を使い、中ボス生成・撃破描画処理は既存のまま使う。
        self.reset_stage(full_reset=True)
        self.scene = "PLAY"
        self.in_boss_room = False
        self.paused = False

        # 中ボスが見える位置からテスト開始。
        if self.midboss:
            self.midboss.alive = True

            if self.stage9_midboss_debug_override_active():
                # Stage9のDEV MIDだけ、sekka2.pyxres tilemap(0,248)から開始。
                # tilemap座標は8pxセル。指定セルを床上面として、その直上へ配置する。
                start_x = DEV_STAGE9_MID_START_TM_X8 * 8
                start_floor_y = DEV_STAGE9_MID_START_TM_Y8 * 8
                self.player.x = float(start_x)
                self.player.y = float(start_floor_y - self.player.h)
                self.player.vx = 0
                self.player.vy = 0
                self.cam_x = int(clamp(start_x, 0, self.TILES_X * TILE - SCREEN_W))
                self.cam_y = int(clamp(start_floor_y - FLOOR_Y, 0, self.TILES_Y * TILE - SCREEN_H))
            else:
                # Stage1～8のDEV MID、および将来の通常処理は従来どおり。
                self.player.x = max(16, self.midboss.x - 96)
                self.player.y = FLOOR_Y - self.player.h
                self.player.vx = 0
                self.player.vy = 0
                self.cam_x = clamp(self.midboss.x - 120, 0, WORLD_W - SCREEN_W)

        # 弾や一時効果が残らないようにする。
        self.bullets.clear()
        self.enemy_bullets.clear()
        self.boss_defeat_timer = 0
        self.defeated_boss = None
        self.defeated_boss_was_stage_boss = False

    def enter_final_boss_phase_test_room(self, phase=1):
        """DEV_MENU専用：Stage9ラスボスを指定フェーズからすぐ試す。"""
        if not self.dev_mode:
            return

        self.dev_midboss_test_active = False
        self.dev_final_phase_test_active = True
        self.dev_final_phase_select = max(1, min(4, int(phase)))

        # 通常のステージ9ボス部屋生成をそのまま使う。
        self.stage = 9
        self.reset_stage(full_reset=True)
        self.enter_boss_room()

        if not self.boss:
            return

        # HP割合でフェーズが決まるため、各フェーズ内に入るHPへ調整する。
        max_hp = int(getattr(self.boss, "max_hp", getattr(self.boss, "hp", 60)) or 60)
        phase_hp_ratio = {
            1: 1.00,  # HP 100%-70%
            2: 0.60,  # HP 70%-40%
            3: 0.30,  # HP 40%-110%
            4: 0.10,  # HP 110%以下
        }
        self.boss.hp = max(1, int(max_hp * phase_hp_ratio[self.dev_final_phase_select]))

        # フェーズ切替直後の内部状態へリセット。
        if self._boss_ai and hasattr(self._boss_ai, "_final_reset_action"):
            self._boss_ai._final_reset_action(self.dev_final_phase_select)
            # デバッグのフェーズ1/3/4はプレイヤー初期位置と重なりやすいため右端へ退避。
            if self.dev_final_phase_select in (1, 3, 4) and hasattr(self._boss_ai, "_final_place_right_edge_safe"):
                self._boss_ai._final_place_right_edge_safe()
                if self.dev_final_phase_select == 3:
                    self._boss_ai._final_phase3_side = "right"
                    self._boss_ai._final_phase3_jump_active = False

        # テスト開始直後に前フェーズ由来の弾・召喚敵が残らないよう掃除。
        self.bullets.clear()
        self.enemy_bullets.clear()
        self.enemies.clear()
        self.boss_stop_timer = 0

        # すぐ試しやすいよう、プレイヤーを少しだけ安全寄りに置く。
        self.player.x = self.boss_left + 32
        self.player.y = FLOOR_Y - self.player.h
        self.player.vx = 0
        self.player.vy = 0
        self.player.invincible_timer = 90
        self.cam_x = clamp(WORLD_W - SCREEN_W, 0, WORLD_W - SCREEN_W)

    def enter_boss_room(self):
        # ボス部屋は環境変化対象外。発動中でも入室時点で即解除する。
        self.set_environment("NONE", announce=False)
        self.environment_elapsed_frames = 0
        self.environment_next_check = ENV_CHECK_INTERVAL_FRAMES
        self.earthquake_warning_timer = 0
        self.earthquake_pending = False

        # ステージ5〜8ボス画像は sekka.pyxres Image2、
        # ステージ9ラスボス画像は sekka2.pyxres Image2 を使う。
        self.use_resource_for_context(self.stage, boss=True)

        # ボス部屋へ入る/リスタートする前に、前回の弾・一時効果を完全に掃除する。
        # これを先に行わないと、ミス後の再入室直後に前回の敵弾で再度ミスになることがある。
        self.bullets.clear()
        self.enemy_bullets.clear()
        self.items.clear()
        self.boss_stop_timer = 0
        self.boss_defeat_timer = 0
        self.defeated_boss = None
        self.defeated_boss_was_stage_boss = False
        self._boss_ai = None

        self.in_boss_room = True
        self.enemies.clear()
        if self.midboss: self.midboss.alive = False
        self.reaper.active = False

        floor_row = FLOOR_Y // TILE
        for tx in range(self.TILES_X):
            for ty in range(floor_row, self.TILES_Y):
                self.level[ty][tx] = SOLID

        self.boss_left = WORLD_W - 240
        self.boss_right = WORLD_W - 16

        # 扉に近すぎないよう、ボス部屋左境界+少しの余白から出現
        start_x = self.boss_left + 32

        boss_def = (STAGE_BOSS_DEF.get(self.stage, {}) or {}).get("boss", DEFAULT_BOSS_DEF)
        start_y = 0 if self.stage == 4 else (FLOOR_Y - boss_def["h"])
        self.boss = Boss(
            start_x,
            start_y,
            hp=boss_def["hp"],
            sprite_key=boss_def["sprite_key"],
        )
        self.boss.w = boss_def["w"]
        self.boss.h = boss_def["h"]
        self.boss.max_hp = boss_def["hp"]

        # stage1: 旧仕様の「プレイヤー方向へ歩き出す」感を維持（必要なければ後で削除OK）
        if self.stage == 1:
            dir = 1 if (self.player.x + self.player.w/2) >= (self.boss.x + self.boss.w/2) else -1
            self.boss.vx = 1.8 * dir

        self.player.x = (self.TILES_X - 6) * TILE
        self.player.y = FLOOR_Y - self.player.h
        self.player.vx = self.player.vy = 0

        self.cam_x = clamp(WORLD_W - SCREEN_W, 0, WORLD_W - SCREEN_W)

        self.scene = "BOSS"
        self.paused = False

        # --- Boss FSM wiring (config-driven; gameplay unchanged) ---
        self._boss_ai = BossAIAdapter(self, self.boss)
        preset = boss_def.get("preset", "stage1_boss")
        self._boss_ai.load_preset(preset)
        # --- Stage 2 boss jump AI timers (pre-jump / in-air / no-shoot) ---
        if self.stage == 2:
            self._s2_jump_cooldown = 180  # 3秒ごとの判定用(60fps想定)
            self._s2_in_jump = False
            self._s2_no_shoot_frames = 0
            self._s2_prejump_frames = 0
            self._s2_land_stop_frames = 0

        dev_short_time_active = False
        if self.dev_mode:
            try:
                dev_short_time_active = DEV_START_TIME_OPTIONS[int(getattr(self, "dev_start_time_index", 0))] is not None
            except Exception:
                dev_short_time_active = False

        # デバッグで30秒/1秒開始を選んだ時は、ボス部屋用の最低45秒補正をかけない。
        if not dev_short_time_active:
            if DEV_BOSS_MIN_SEC is not None:
                min_boss_sec = int(DEV_BOSS_MIN_SEC)
                if self.time_limit < min_boss_sec * 60:
                    self.time_limit = min_boss_sec * 60

            if self.time_limit < 45 * 60:
                self.time_limit = 45 *60

    def spawn_item_from_block(self, tx, ty):
        
        weighted = ["POWER","POWER","POWER", "BIGPTS","ARMOR","1UP"]
        itype = random.choice(weighted)
        ix = tx * TILE; iy = ty * TILE - 12
        try:
            self.items.append(Item(ix, iy, itype))
            play_sfx("ITEM_APPEAR")
        except NameError:
            # 安全策: クラス読み込み順の問題を避ける
            from math import floor
            self.items = getattr(self, 'items', [])
            self.items.append(Item(ix, iy, itype))
            play_sfx("ITEM_APPEAR")


    def break_or_bump(self, tx, ty):
        tt = tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty)

        if tt == TILE_BREAK:
            self.level[ty][tx] = EMPTY
            put_kind(tx, ty, "AIR")
            play_sfx("BLOCK_BREAK")

            # 壊せるブロック報酬
            # 10% : アイテムボックスと同様
            # 20%: 100点コイン出現
            # 710%: 何もなし
            r = random.random()

            if r < 0.10:
                self.spawn_item_from_block(tx, ty)

            elif r < 0.25:
                self.level[ty][tx] = TILE_COIN
                put_kind(tx, ty, "COIN")

        elif tt == TILE_ITEM:
            play_sfx("BLOCK_BUMP")
            self.level[ty][tx] = EMPTY
            put_kind(tx, ty, "AIR")
            self.spawn_item_from_block(tx, ty)

        elif tt == TILE_BLOCK:
            # 壊せないブロックを下から叩いた時の鈍い音
            play_sfx("BLOCK_DULL")

    def update_ghost_floor_sfx(self):
        """消える床(AUTO/TILE_GHOST)の出現・消失時にワープ音を鳴らす。"""
        try:
            tiles = getattr(self, "ghost_tiles", None)
            if not tiles:
                self._ghost_visible_prev = None
                return
            visible = (pyxel.frame_count // 90) % 2 == 0
            prev = getattr(self, "_ghost_visible_prev", None)
            if prev is None:
                self._ghost_visible_prev = visible
                return
            if visible != prev:
                # 画面内にある消える床が切り替わった時だけ鳴らす。
                for (tx, ty) in tiles:
                    if is_rect_on_screen(tx * TILE, ty * TILE, TILE, TILE, margin=16):
                        play_sfx("WARP")
                        break
                self._ghost_visible_prev = visible
        except Exception:
            pass

    def update_step_blocks(self):
        """踏んだあと一定時間後に壊れるブロック(CRASH)の処理"""

        # ---- 1) すでにカウントダウン中のブロックを更新 ----
        timers = getattr(self, "step_break_timers", None)
        if timers is not None:
            to_break = []
            for pos in list(timers.keys()):
                timers[pos] -= 1
                if timers[pos] <= 0:
                    to_break.append(pos)

            for (tx, ty) in to_break:
                # タイマーから削除
                timers.pop((tx, ty), None)
                # CRASHリストからも削除
                tiles = getattr(self, "step_break_tiles", None)
                if tiles is not None:
                    tiles.discard((tx, ty))

                # 実際にブロックを消す
                # TILES_X/Y が self に無い場合に備えて WORLD_ から計算する
                tiles_x = getattr(self, "TILES_X", WORLD_W // TILE)
                tiles_y = getattr(self, "TILES_Y", WORLD_H // TILE)
                if 0 <= tx < tiles_x and 0 <= ty < tiles_y:
                    self.level[ty][tx] = EMPTY      # 当たり判定を空に
                    put_kind(tx, ty, "AIR")         # エディタ側も AIR に
                    # 踏むと壊れるブロックも、通常の壊せるブロックと同じ破壊音にする。
                    play_sfx_at("BLOCK_BREAK", tx * TILE, ty * TILE, TILE, TILE, margin=16)

        # ---- 2) 新しく踏まれたCRASHブロックにタイマーをセット ----
        tiles = getattr(self, "step_break_tiles", None)
        if not tiles:
            return
        if not self.player or not self.player.alive:
            return

        # 足元タイル
        foot_x = self.player.x + self.player.w // 2
        foot_y = self.player.y + self.player.h + 1
        tx = int(foot_x // TILE)
        ty = int(foot_y // TILE)

        # 範囲外なら無視
        tiles_x = getattr(self, "TILES_X", WORLD_W // TILE)
        tiles_y = getattr(self, "TILES_Y", WORLD_H // TILE)
        if not (0 <= tx < tiles_x and 0 <= ty < tiles_y):
            return

        # ちゃんと地面に乗っているときだけ
        if not self.player.on_ground:
            return

        pos = (tx, ty)

        if pos in tiles:
            # タイマーdictがなければ作成
            timers = getattr(self, "step_break_timers", None)
            if timers is None:
                timers = {}
                self.step_break_timers = timers

            # まだカウント開始していないときだけセット
            if pos not in timers:
                delay = getattr(self, "STEP_BREAK_DELAY_FRAMES", 30)
                timers[pos] = max(1, int(delay))

    def _toggle_dev_mode_from_title(self):
        """タイトル画面のデバッグモードを切り替える。既存／追加コマンド共通処理。"""
        self.dev_mode = not self.dev_mode
        play_title_select_sfx()
        self.dev_menu_index = 0
        # 通常モードへ戻す時は、デバッグ専用状態を残さない。
        if not self.dev_mode:
            self.dev_player_invincible = False
            self.dev_environment_index = 0

    def _update_title_dash_hold_debug_toggle(self):
        """TITLEで、設定済みDASH入力を2秒長押しした時に一度だけ切り替える。"""
        if input_dash():
            # 既に発動済みなら、離されるまで再発動させない。
            if self.title_dash_hold_triggered:
                return False
            self.title_dash_hold_frames += 1
            if self.title_dash_hold_frames >= DASH_HOLD_COMMAND_FRAMES:
                self.title_dash_hold_frames = DASH_HOLD_COMMAND_FRAMES
                self.title_dash_hold_triggered = True
                self._toggle_dev_mode_from_title()
                return True
        else:
            self.title_dash_hold_frames = 0
            self.title_dash_hold_triggered = False
        return False

    def _update_pause_dash_hold_to_title(self):
        """PLAY/BOSSのポーズ中、設定済みDASH入力を2秒長押ししてタイトルへ戻す。"""
        if not getattr(self, "paused", False):
            self.pause_dash_hold_frames = 0
            self.pause_dash_hold_triggered = False
            return False

        if input_dash():
            # 発動後は離されるまで再発動させない（通常はgoto_titleで即リセットされる）。
            if self.pause_dash_hold_triggered:
                return False
            self.pause_dash_hold_frames += 1
            if self.pause_dash_hold_frames >= DASH_HOLD_COMMAND_FRAMES:
                self.pause_dash_hold_frames = DASH_HOLD_COMMAND_FRAMES
                self.pause_dash_hold_triggered = True
                self.goto_title()
                return True
        else:
            self.pause_dash_hold_frames = 0
            self.pause_dash_hold_triggered = False
        return False

    def update(self):
        self.update_scene_music(restart=False)

        # DEBUG INVINCIBLE OFF だけ、一定時間後に自動で消す。
        # ON表示は従来どおり表示継続。MISS / RETRY は update_effect_timers() 側で管理。
        if getattr(self, "screen_notice_text", "") == "DEBUG INVINCIBLE OFF" and getattr(self, "screen_notice_timer", 0) > 0:
            self.screen_notice_timer -= 1
            if self.screen_notice_timer <= 0:
                self.screen_notice_text = ""
                self.screen_notice_timer = 0

        if self.scene == "TITLE":

            # ===== HIDDEN DEBUG MODE TOGGLE =====
            # 追加: CONFIGで「DASH (HOLD)」に割り当てたキー／ボタンを2秒長押し。
            # 既存: Keyboard=Pを押している間にZ / Gamepad=STARTを押している間にX。
            dash_hold_toggled = self._update_title_dash_hold_debug_toggle()
            debug_toggle_keyboard = pyxel.btn(pyxel.KEY_P) and pyxel.btnp(pyxel.KEY_Z)
            debug_toggle_gamepad = (
                _gp_btn("GAMEPAD1_BUTTON_START")
                and _gp_btnp("GAMEPAD1_BUTTON_X")
            )
            if (debug_toggle_keyboard or debug_toggle_gamepad) and not dash_hold_toggled:
                self._toggle_dev_mode_from_title()
                # 既存コマンドにDASH割り当てキーが含まれていた場合も、
                # そのまま押し続けて2秒後に再反転しないよう、離すまでロックする。
                self.title_dash_hold_frames = 0
                self.title_dash_hold_triggered = bool(input_dash())

            # ===== DEV SELECT (TITLE): all items use cursor selection =====
            if self.dev_mode:
                # 0:STAGE / 1:BOSS / 2:MIDBOSS / 3:FINAL / 4:TIME / 5:ENV
                dev_item_count = 6

                if input_up_pressed():
                    self.dev_menu_index = (int(getattr(self, "dev_menu_index", 0)) - 1) % dev_item_count
                    play_title_select_sfx()
                if input_down_pressed():
                    self.dev_menu_index = (int(getattr(self, "dev_menu_index", 0)) + 1) % dev_item_count
                    play_title_select_sfx()

                selected = int(getattr(self, "dev_menu_index", 0))
                left_pressed = input_left_pressed()
                right_pressed = input_right_pressed()

                if left_pressed or right_pressed:
                    delta = -1 if left_pressed else 1
                    if selected == 0:
                        self.dev_stage_select = max(1, min(self.max_stage, self.dev_stage_select + delta))
                    elif selected in (1, 2):
                        self.dev_boss_stage_select = max(1, min(self.max_stage, self.dev_boss_stage_select + delta))
                    elif selected == 3:
                        self.dev_final_phase_select = max(1, min(4, self.dev_final_phase_select + delta))
                    elif selected == 4:
                        self.dev_start_time_index = (int(getattr(self, "dev_start_time_index", 0)) + delta) % len(DEV_START_TIME_OPTIONS)
                    elif selected == 5:
                        self.dev_environment_index = (int(getattr(self, "dev_environment_index", 0)) + delta) % len(ENV_TYPES)
                    play_title_select_sfx()

                if input_decide_pressed():
                    if selected == 0:
                        # Start selected stage.
                        self.stop_scene_music()
                        play_title_start_sfx()
                        self.dev_midboss_test_active = False
                        self.dev_final_phase_test_active = False
                        self.stage = self.dev_stage_select
                        self.lives = 5
                        self.score = 0
                        self.next_extend = 10000
                        # DEV STAGEは「通常ステージを最初から」確認するモード。
                        # 前のDEV MID/BOSS撃破状態や撃破タイマーを持ち越さない。
                        self.boss_defeat_timer = 0
                        self.defeated_boss = None
                        self.dev_midboss_test_active = False
                        self.dev_final_phase_test_active = False
                        if int(self.stage) == 9:
                            self.stage9_midboss_cleared = False
                            self.stage9_midboss_cleared_key = None
                            self.stage9_midboss_unlock_effect_done = False
                            self.stage9_midboss_unlock_timer = 0
                        self.reset_stage(full_reset=True)
                        self.scene = "PLAY"
                        if DEV_FORCE_LIVES is not None:
                            self.lives = int(DEV_FORCE_LIVES)

                    elif selected == 1:
                        # Start selected boss test.
                        self.stop_scene_music()
                        play_title_start_sfx()
                        self.dev_midboss_test_active = False
                        self.dev_final_phase_test_active = False
                        self.stage = self.dev_boss_stage_select
                        self.lives = 5
                        self.score = 0
                        self.next_extend = 10000
                        self.reset_stage(full_reset=True)
                        self.enter_boss_room()
                        if DEV_FORCE_LIVES is not None:
                            self.lives = int(DEV_FORCE_LIVES)

                    elif selected == 2:
                        # Start selected midboss test.
                        self.stop_scene_music()
                        play_title_start_sfx()
                        self.stage = self.dev_boss_stage_select
                        self.lives = 5
                        self.score = 0
                        self.next_extend = 10000
                        self.enter_midboss_test_room()
                        if DEV_FORCE_LIVES is not None:
                            self.lives = int(DEV_FORCE_LIVES)

                    elif selected == 3:
                        # Start Stage9 final boss from selected phase.
                        self.stop_scene_music()
                        play_title_start_sfx()
                        self.lives = 5
                        self.score = 0
                        self.next_extend = 10000
                        self.enter_final_boss_phase_test_room(self.dev_final_phase_select)
                        if DEV_FORCE_LIVES is not None:
                            self.lives = int(DEV_FORCE_LIVES)

                    elif selected == 4:
                        # TIME is a setting item: RETURN also advances the value.
                        self.dev_start_time_index = (int(getattr(self, "dev_start_time_index", 0)) + 1) % len(DEV_START_TIME_OPTIONS)
                        play_title_select_sfx()

                    elif selected == 5:
                        # ENV is a setting item: RETURN also advances the value.
                        self.dev_environment_index = (int(getattr(self, "dev_environment_index", 0)) + 1) % len(ENV_TYPES)
                        play_title_select_sfx()

            # ===== NORMAL TITLE MENU: cursor selection =====
            if not self.dev_mode:
                title_item_count = 3  # START / CONTINUE / CONFIG
                if input_up_pressed():
                    self.title_menu_index = (int(getattr(self, "title_menu_index", 0)) - 1) % title_item_count
                    play_title_select_sfx()
                if input_down_pressed():
                    self.title_menu_index = (int(getattr(self, "title_menu_index", 0)) + 1) % title_item_count
                    play_title_select_sfx()

                # Existing A/RETURN works as before. Configured START/PAUSE can also decide,
                # which is useful on the browser virtual pad.
                if input_decide_pressed() or input_start_pause_pressed():
                    selected = int(getattr(self, "title_menu_index", 0))
                    continue_available = (
                        self.last_failed_stage is not None and
                        self.score >= Game.CONTINUE_COST
                    )

                    if selected == 0:
                        self.stop_scene_music()
                        play_title_start_sfx()
                        self.dev_midboss_test_active = False
                        self.stage = 1
                        self.lives = 5
                        self.score = 0
                        self.next_extend = 10000
                        self.scored_enemy_keys.clear()
                        self.scored_boss_keys.clear()
                        self.stage9_gem_count = 0
                        self.stage9_gem_dropped_keys.clear()
                        self.stage9_pending_gems.clear()
                        self.stage9_gems.clear()
                        self.stage9_midboss_cleared = False
                        self.stage9_midboss_cleared_key = None
                        self.stage9_hint_timer = 0
                        self.stage_miss_counts.clear()
                        self.clear_bonus_applied_stage = None
                        self.final_life_bonus = 0
                        self.stage9_reached = False
                        self.reset_stage(full_reset=True)
                        self.scene = "PLAY"
                        if DEV_FORCE_LIVES is not None:
                            self.lives = int(DEV_FORCE_LIVES)
                    elif selected == 1 and continue_available:
                        self.stop_scene_music()
                        play_title_start_sfx()
                        self.dev_midboss_test_active = False
                        self.score -= Game.CONTINUE_COST
                        self.stage = self.last_failed_stage
                        if int(self.stage) == 9:
                            self.stage9_reached = True
                        self.lives = 3
                        self.reset_stage(full_reset=True)
                        self.scene = "PLAY"
                        self.paused = False
                        if DEV_FORCE_LIVES is not None:
                            self.lives = int(DEV_FORCE_LIVES)
                    elif selected == 2:
                        play_title_select_sfx()
                        self.config_menu_index = 0
                        self.config_capture_action = None
                        self.scene = "CONFIG"
                    else:
                        # CONTINUE unavailable.
                        play_title_select_sfx()

        elif self.scene == "CONFIG":
            actions = ["JUMP", "SHOT", "DASH", "START_PAUSE"]
            capture_action = getattr(self, "config_capture_action", None)

            if capture_action is not None:
                # Accept whichever comes first: a keyboard key or a physical/virtual gamepad button.
                # Arrow keys / D-pad are excluded so movement remains fixed.
                pressed_key = _first_configurable_keyboard_key_pressed()
                pressed_name = _first_configurable_gamepad_button_pressed()
                if pressed_key is not None:
                    KEYBOARD_BINDINGS[capture_action] = pressed_key
                    self.config_capture_action = None
                    play_title_select_sfx()
                elif pressed_name is not None:
                    GAMEPAD_BINDINGS[capture_action] = pressed_name
                    self.config_capture_action = None
                    play_title_select_sfx()
                # ESC cancels capture without changing anything.
                elif pyxel.btnp(pyxel.KEY_ESCAPE):
                    self.config_capture_action = None
                    play_title_select_sfx()
            else:
                item_count = 6  # 4 bindings + RESET + BACK
                if input_up_pressed():
                    self.config_menu_index = (int(getattr(self, "config_menu_index", 0)) - 1) % item_count
                    play_title_select_sfx()
                if input_down_pressed():
                    self.config_menu_index = (int(getattr(self, "config_menu_index", 0)) + 1) % item_count
                    play_title_select_sfx()

                selected = int(getattr(self, "config_menu_index", 0))
                # Use RETURN/A only here to avoid a custom START/PAUSE binding immediately
                # triggering itself while entering capture mode.
                if input_decide_pressed():
                    if selected < 4:
                        self.config_capture_action = actions[selected]
                        play_title_select_sfx()
                    elif selected == 4:
                        KEYBOARD_BINDINGS.clear()
                        KEYBOARD_BINDINGS.update(DEFAULT_KEYBOARD_BINDINGS)
                        GAMEPAD_BINDINGS.clear()
                        GAMEPAD_BINDINGS.update(DEFAULT_GAMEPAD_BINDINGS)
                        play_title_select_sfx()
                    else:
                        self.scene = "TITLE"
                        self.title_menu_index = 2
                        play_title_select_sfx()
                elif pyxel.btnp(pyxel.KEY_ESCAPE) or _gp_btnp("GAMEPAD1_BUTTON_BACK"):
                    self.scene = "TITLE"
                    self.title_menu_index = 2
                    play_title_select_sfx()

        elif self.scene == "PLAY":
            if self.update_effect_timers():
                return
            if self.update_environment():
                return

            # デバッグプレイ中のみ: Iキーでプレイヤー無敵ON/OFF。
            # 敵・弾・爆風などの通常被弾だけ無効化し、奈落/タイムアウトは通常どおりミスにする。
            if self.dev_mode and input_dev_invincible_pressed():
                self.dev_player_invincible = not getattr(self, "dev_player_invincible", False)
                self.screen_notice_text = "DEBUG INVINCIBLE ON" if self.dev_player_invincible else "DEBUG INVINCIBLE OFF"
                self.screen_notice_timer = 0 if self.dev_player_invincible else 60
                if not self.dev_player_invincible and self.player:
                    self.player.invincible_timer = 0

            if self.dev_mode and getattr(self, "dev_player_invincible", False) and self.player:
                self.player.invincible_timer = max(getattr(self.player, "invincible_timer", 0), 999999)

            if input_pause_pressed():
                self.paused = not self.paused
                if self.paused:
                    self.stop_scene_music()
                else:
                    self.pause_dash_hold_frames = 0
                    self.pause_dash_hold_triggered = False
                    self.update_scene_music(restart=True)
                play_pause_toggle_sfx()
                return
            if self.paused:
                # 追加: CONFIGで「DASH (HOLD)」に割り当てたキー／ボタンを2秒長押し。
                if self._update_pause_dash_hold_to_title():
                    return
                # 既存のタイトル復帰コマンドも維持。
                if input_back_to_title_pressed():
                    self.goto_title()
                    return
                if not input_pause_skip_pressed():
                    return

            for it in self.items: it.update()

            # --- Player shooting (tap = normal / hold->release = charged if powered) ---
            z_now = input_shot_held()

            if self.player.pstate != "ATTACK":
            # 通常弾（ATTACKじゃない＝NONE/ARMOR）

                if input_shot_pressed() and self.player.shot_cd == 0:
                    dir_vx = 3 * (1 if self.player.face >= 0 else -1)
                    bx = self.player.x + (self.player.w if dir_vx > 0 else -8)
                    by = self.player.y + self.player.h // 2
                    b = Bullet(bx, by, dir_vx, power = 1)
                    b.kind = "normal"
                    self.bullets.append(b)
                    play_sfx("SHOT")
                    self.player.shot_cd = 10
            else:
                # パワーアップ中:押している間はチャージ
                if z_now and self.player.shot_cd == 0:
                    self.charging = True
                    self.charge_frames = min(self.charge_frames + 1, CHARGE_NEED_FRAMES + 15)

                # 「離した瞬間」= 前フレーム押していた & 今フレーム押していない
                if (not z_now) and self.prev_z and self.player.shot_cd == 0 and self.charging:
                    dir_vx = 3 * (1 if self.player.face >= 0 else -1)
                    bx = self.player.x + (self.player.w if dir_vx > 0 else -8)
                    by = self.player.y + self.player.h // 2

                    if self.charge_frames >= CHARGE_NEED_FRAMES:
                        # === Charged shot ===(X据え置き 6px / Y拡大 30px / センタリング)
                        big = Bullet(bx, by, dir_vx, power = 2)
                        big.kind = "power"
                        big.w = 6
                        big.h = 30
                        big.y = by - big.h // 2 # 完全センタリング。床に触れにくくなる。
                        self.bullets.append(big)
                        play_sfx("CHARGE_SHOT")
                    else:
                        # 短押し:通常弾
                        b = Bullet(bx, by, dir_vx, power = 1)
                        b.kind = "normal"
                        self.bullets.append(b)
                        play_sfx("SHOT")

                    self.player.shot_cd = 10
                    self.charging = False
                    self.charge_frames = 0

            # 最後に prev_z を更新
            self.prev_z = z_now
            # --- /shooting ---

            # --- spring flash timer update ---
            if self.spring_flash:
                dead = []
                for k in self.spring_flash:
                    self.spring_flash[k] -= 1
                    if self.spring_flash[k] <= 0:
                        dead.append(k)
                for k in dead:
                    del self.spring_flash[k]

            self.update_ghost_floor_sfx()
            self.player.update(self.level, self.TILES_X, self.TILES_Y, self.platforms)
            # プレイヤーが乗った瞬間に壊れる/消えるブロック処理
            self.update_step_blocks()

            # --- Camera follow (robust) ---

            # --- Camera follow (robust) ---
            vw = SCREEN_W
            mw = self.TILES_X * TILE
            px = getattr(getattr(self, 'player', None), 'x', 0)
            center = min(96, vw // 2)
            target = int(px - center)
            self.cam_x = int(clamp(target, 0, mw - vw))
            vw, vh = 256, 256
            mh = self.TILES_Y * TILE
            py = getattr(getattr(self, 'player', None), 'y', 0)
            # Stage9のみ縦スクロール。通常ステージは cam_y=0 のまま。
            if mh > vh:
                target_y = int(py - 112)
                self.cam_y = int(clamp(target_y, 0, mh - vh))
            else:
                self.cam_y = 0

            # 奈落は「そのステージの一番下」だけ。Stage9では768px下端まで落ちてからミス。
            if self.player.y > mh:
                self.player.alive = False
                self.player.death_cause = "void"
            if not self.player.alive and getattr(self.player, "death_cause", "") == "void":
                self.lose_life(kind="void"); return

            if self.player.head_hit_tiles:
                for (tx, ty) in self.player.head_hit_tiles:
                    self.break_or_bump(tx, ty)
                self.player.head_hit_tiles.clear()

            for p in self.platforms:
                p.update()

            l, r, t, b = rect_to_tiles(self.player.x, self.player.y, self.player.w, self.player.h)
            for ty in range(t, b + 1):
                for tx in range(l, r + 1):
                    if tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty) == TILE_DOOR:
                        play_sfx_at("BOSS_DOOR", tx * TILE, ty * TILE, TILE, TILE)
                        self.enter_boss_room()
                        return

            if not self.update_midboss_explosion_effect():
                return

            if (self.midboss and self.midboss.alive
                    and normal_stage4_midboss_active(self)):
                # --- Midboss FSM tick (config-driven) ---
                if (not getattr(self, "paused", False)) and getattr(self, "_midboss_ai", None):
                    self._midboss_ai.update()

                # Stage4中ボス(Flyer型)は BossAIAdapter 側で通常Flyer相当の移動を完結させる。
                # それ以外は従来どおり Boss.update の横移動を使う。
                if not getattr(self.midboss, "_skip_default_midboss_update", False):
                    self.midboss.update(left=WORLD_W - 240, right=WORLD_W - 64)
                if can_stomp(self.player, self.midboss, 0.5, 8, 4):
                    # Stage9 dedicated midboss is completely damage-locked until 15 gems are collected.
                    if self.stage9_midboss_gem_lock_active():
                        play_sfx_at("METAL_REFLECT", self.midboss.x, self.midboss.y, self.midboss.w, self.midboss.h)
                        self.player.vy = JUMP_VY * 0.5
                    # 無敵中の中ボス（例：Stage8ジャンプ中）は踏んでも撃破扱いにせず、接触ミス扱い。
                    elif getattr(self.midboss, "invincible", False):
                        if self.player.invincible_timer <= 0:
                            self.lose_life(); return
                    # stage5_mid: StompDamageWalker流用。踏んだ側（プレイヤー）がダメージ。
                    elif getattr(self.midboss, "stomp_damage", False):
                        if self.player.invincible_timer <= 0:
                            self.lose_life(); return
                    else:
                        play_sfx_at("STOMP", self.midboss.x, self.midboss.y, self.midboss.w, self.midboss.h)
                        stomp_base = 1
                        stomp_dmg = int(stomp_base * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0))
                        self.midboss.damage(stomp_dmg)
                        if not self.midboss.alive:
                            self.start_boss_defeat_effect(self.midboss, was_stage_boss=False)
                            return
                        self.player.vy = JUMP_VY * 0.7
                elif aabb(self.player.x, self.player.y, self.player.w, self.player.h,
                        self.midboss.x, self.midboss.y, self.midboss.w, self.midboss.h):
                    if self.player.invincible_timer <= 0:
                        self.lose_life(); return

            # Stage9 TM2マーカー配置のフィールド中ボス/ボス。
            # 通常ステージの self.midboss / ボス部屋 self.boss とは別枠で処理する。
            _stage9_field_groups = [
                (getattr(self, "field_midbosses", []), getattr(self, "_field_midboss_ais", []), 500),
                (getattr(self, "field_bosses", []), getattr(self, "_field_boss_ais", []), 1000),
            ]
            for _actors, _ais, _defeat_score in _stage9_field_groups:
                if not _actors:
                    continue
                for idx, fb in enumerate(list(_actors)):
                    if not fb.alive:
                        continue
                    if not stage9_field_actor_active(self, fb):
                        continue
                    try:
                        ai = _ais[idx]
                    except Exception:
                        ai = None

                    # Stage1ボス由来の場合、ボス部屋と同じ「停止→5way扇状ショット」を再現。
                    # 通常の self.boss_shot_cd はボス部屋専用なので、フィールド配置個体ごとに持たせる。
                    if (int(getattr(fb, "field_boss_origin_stage", 0)) == 1
                            and not bool(getattr(fb, "is_midboss", False))):
                        if getattr(fb, "field_boss_stop_timer", 0) > 0:
                            fb.field_boss_stop_timer -= 1
                            fb.anim_state = "stop"
                            fb.vx = 0
                        else:
                            # Stage9フィールド内のStage1ボス専用ショット停止から復帰する時、
                            # 直前に保存した向きが古いままだと右端で正方向へ戻され続ける。
                            # 現在位置が端なら、必ず範囲内へ戻る向きに補正してから巡回再開する。
                            _restore_vx = getattr(fb, "field_boss_prev_vx", 0)
                            _left = int(getattr(fb, "field_boss_left", max(0, int(fb.x) - 160)))
                            _right = int(getattr(fb, "field_boss_right", min(WORLD_W, int(fb.x) + 224)))
                            _bw = int(getattr(fb, "w", 64))
                            if float(getattr(fb, "x", 0.0)) <= _left:
                                _restore_vx = abs(float(_restore_vx or 1.6))
                            elif float(getattr(fb, "x", 0.0)) >= _right - _bw:
                                _restore_vx = -abs(float(_restore_vx or 1.6))
                            if _restore_vx:
                                fb.vx = _restore_vx
                            fb.anim_state = "walk"

                            if getattr(fb, "field_boss_shot_cd", 0) > 0:
                                fb.field_boss_shot_cd -= 1
                            else:
                                bx = int(fb.x + getattr(fb, "w", 64) // 2)
                                by = int(fb.y + getattr(fb, "h", 64) // 2)
                                player_cx = self.player.x + getattr(self.player, "w", 16) / 2
                                player_cy = self.player.y + getattr(self.player, "h", 16) / 2
                                base_ang = math.atan2(player_cy - by, player_cx - bx)
                                speed = 2.2
                                for deg in (-20, -10, 0, 10, 20):
                                    rad = base_ang + math.radians(deg)
                                    vx = speed * math.cos(rad)
                                    vy = speed * math.sin(rad)
                                    self.spawn_enemy_bullet(bx, by, vx, vy, tag="boss")
                                fb.field_boss_prev_vx = getattr(fb, "vx", 0)
                                fb.vx = 0
                                fb.field_boss_stop_timer = 18
                                fb.field_boss_shot_cd = 120

                    if getattr(fb, "field_boss_stop_timer", 0) <= 0:
                        # Stage9フィールド配置版の各ボス/中ボスに、通常ボス部屋用の
                        # boss_left/right と boss_stop_timer を一時的に渡す。
                        #
                        # これをしないと、
                        # ・Stage4ボスのフライヤー召喚が None の boss_left/right を参照して落ちる
                        # ・Stage8ボスの停止/ジャンプ後停止が共有タイマーで固まる
                        # ・Stage3/7系の端・床位置が通常ボス部屋基準になる
                        # など、ステージ9マーカー配置と通常ボス部屋の状態が混ざる。
                        _old_boss_left = getattr(self, "boss_left", None)
                        _old_boss_right = getattr(self, "boss_right", None)
                        _old_boss_stop_timer = getattr(self, "boss_stop_timer", 0)
                        _old_active_boss = getattr(self, "boss", None)
                        _field_ai_stop = int(getattr(fb, "field_boss_ai_stop_timer", 0))

                        self.boss_left = int(getattr(fb, "field_boss_left", max(0, int(fb.x) - 160)))
                        self.boss_right = int(getattr(fb, "field_boss_right", min(WORLD_W, int(fb.x) + 224)))
                        self.boss_stop_timer = _field_ai_stop

                        # 通常ステージ6では BossFSM の一部処理が Game.boss を参照して
                        # 扇ショット中の防御状態を設定する。Stage9歴代ボスは field_bosses
                        # 別管理のため、その参照先が空/別個体となり、弱点状態が残っていた。
                        # Stage9のStage6ボスを更新する間だけ active boss として束縛し、
                        # 通常ステージ6と同じAIコールバック経路を通す。
                        _bind_stage9_stage6_as_active_boss = (
                            int(getattr(fb, "field_boss_origin_stage", 0) or 0) == 6
                            and not bool(getattr(fb, "is_midboss", False))
                        )
                        if _bind_stage9_stage6_as_active_boss:
                            self.boss = fb

                        try:
                            if self.boss_stop_timer > 0:
                                self.boss_stop_timer -= 1
                                fb.vx = 0.0
                                fb.anim_state = "stop"
                            else:
                                if (not getattr(self, "paused", False)) and ai:
                                    ai.update()
                                if not getattr(fb, "_skip_default_midboss_update", False):
                                    left = int(getattr(fb, "field_boss_left", max(0, int(fb.x) - 160)))
                                    right = int(getattr(fb, "field_boss_right", min(WORLD_W, int(fb.x) + 224)))
                                    fb.update(left=left, right=right)
                                    # Stage1ボスはショット停止復帰用に直近の巡回方向を保存する。
                                    # Boss.update() 後の値を保存することで、右端/左端で反転した向きが失われない。
                                    if (int(getattr(fb, "field_boss_origin_stage", 0)) == 1
                                        and not bool(getattr(fb, "is_midboss", False))
                                        and float(getattr(fb, "vx", 0.0)) != 0.0):
                                        fb.field_boss_prev_vx = getattr(fb, "vx", 0)
                            fb.field_boss_ai_stop_timer = int(max(0, getattr(self, "boss_stop_timer", 0)))
                        finally:
                            self.boss_left = _old_boss_left
                            self.boss_right = _old_boss_right
                            self.boss_stop_timer = _old_boss_stop_timer
                            if _bind_stage9_stage6_as_active_boss:
                                self.boss = _old_active_boss

                    # AI移動後もマーカー範囲内に収める。
                    left = getattr(fb, "field_boss_left", None)
                    right = getattr(fb, "field_boss_right", None)
                    if left is not None and right is not None:
                        fb.x = clamp(fb.x, int(left), int(right) - int(getattr(fb, "w", 32)))

                    top = getattr(fb, "field_boss_top", None)
                    bottom = getattr(fb, "field_boss_bottom", None)
                    if top is not None and bottom is not None:
                        fb.y = clamp(fb.y, int(top), int(bottom) - int(getattr(fb, "h", 32)))

                    is_stage9_stage5_boss = (
                        int(getattr(self, "stage", 0)) == 9
                        and int(getattr(fb, "field_boss_origin_stage", 0)) == 5
                        and not bool(getattr(fb, "is_midboss", False))
                    )
                    is_stage9_stage6_boss = (
                        int(getattr(self, "stage", 0)) == 9
                        and int(getattr(fb, "field_boss_origin_stage", 0)) == 6
                        and not bool(getattr(fb, "is_midboss", False))
                    )
                    field_boss_contact = aabb(
                        self.player.x, self.player.y, self.player.w, self.player.h,
                        fb.x, fb.y, fb.w, fb.h
                    )

                    # Stage9歴代Stage6ボス限定：通常Stage6ボスのAI状態と
                    # ボス部屋側のガード踏み処理を、そのままフィールド個体へ適用する。
                    #
                    # can_stomp() はAABB接触より最大4px早く成立する。以前はこの専用分岐を
                    # field_boss_contact(AABB)だけで開始していたため、その4px区間では下の
                    # 汎用ボス処理へ抜け、常時HPダメージ＋通常踏み音になっていた。
                    stage9_stage6_stomp_probe = (
                        can_stomp(self.player, fb, 0.5, 8, 4)
                        if is_stage9_stage6_boss else False
                    )
                    if is_stage9_stage6_boss and (field_boss_contact or stage9_stage6_stomp_probe):
                        player_hurt_blocked = (getattr(self.player, "invincible_timer", 0) > 0)
                        stomp_ok = bool(stage9_stage6_stomp_probe)

                        # 通常ステージ6と同じ、上面接触の救済判定。
                        px_l = self.player.x
                        px_r = self.player.x + self.player.w
                        py_t = self.player.y
                        py_f = self.player.y + self.player.h
                        ex_l = fb.x - 8
                        ex_r = fb.x + fb.w + 8
                        ey_t = fb.y
                        ey_top_zone = fb.y + fb.h * 0.62
                        shield_top_ok = (
                            (px_r > ex_l and px_l < ex_r)
                            and (py_f >= ey_t - 8 and py_f <= ey_top_zone + 6)
                            and (py_t < ey_t + fb.h * 0.35)
                        )
                        stomp_ok = stomp_ok or shield_top_ok

                        # 小ジャンプ中は通常ステージ6同様、接触でプレイヤーミス。
                        if getattr(fb, "jump_contact_damage", False):
                            if not player_hurt_blocked:
                                self.lose_life(); return
                            continue

                        if stomp_ok:
                            # 通常ステージ6と同じ順序。弱点中はSTOMPが残り、
                            # 防御中は同一効果音チャンネルのMETAL_REFLECTで置き換わる。
                            play_sfx_at("STOMP", fb.x, fb.y, fb.w, fb.h)
                            if getattr(fb, "_stomp_vulnerable", False):
                                stomp_base = 1
                                stomp_dmg = int(stomp_base * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0))
                                fb.damage(stomp_dmg)
                                if not fb.alive:
                                    self.start_boss_defeat_effect(fb, was_stage_boss=False)
                                    continue
                                self.player.vy = JUMP_VY * 0.7
                            else:
                                play_sfx_at("METAL_REFLECT", fb.x, fb.y, fb.w, fb.h)
                                self.player.vy = JUMP_VY * 0.55
                            continue

                        # 横・下側からの接触も通常ステージ6と同じくプレイヤーミス。
                        if not player_hurt_blocked:
                            self.lose_life(); return
                        continue

                    if can_stomp(self.player, fb, 0.5, 8, 4):
                        if getattr(fb, "invincible", False) or getattr(fb, "stomp_damage", False):
                            if self.player.invincible_timer <= 0:
                                # Stage9歴代Stage5ボス限定：踏みつけミスの瞬間にも
                                # 爆発エフェクトと爆発SEを必ず出す。
                                if is_stage9_stage5_boss:
                                    hit_x = clamp(self.player.x + self.player.w * 0.5, fb.x, fb.x + fb.w)
                                    hit_y = clamp(self.player.y + self.player.h, fb.y, fb.y + fb.h)
                                    self.spawn_stage5_boss_hit_effect(hit_x, hit_y, actor=fb)
                                self.lose_life()
                                if is_stage9_stage5_boss:
                                    # ミス音/ミス曲開始後に別チャンネルで鳴らし、爆発音が消されないようにする。
                                    play_sfx_at_ch(2, "EXPLOSION", fb.x, fb.y, fb.w, fb.h, margin=24)
                                return
                        else:
                            play_sfx_at("STOMP", fb.x, fb.y, fb.w, fb.h)
                            if is_stage9_stage5_boss:
                                hit_x = clamp(self.player.x + self.player.w * 0.5, fb.x, fb.x + fb.w)
                                hit_y = clamp(self.player.y + self.player.h, fb.y, fb.y + fb.h)
                                self.spawn_stage5_boss_hit_effect(hit_x, hit_y, actor=fb)
                            stomp_base = 1
                            stomp_dmg = int(stomp_base * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0))
                            fb.damage(stomp_dmg)
                            if not fb.alive:
                                self.start_boss_defeat_effect(fb, was_stage_boss=False)
                                continue
                            self.player.vy = JUMP_VY * 0.7
                    elif field_boss_contact:
                        if is_stage9_stage5_boss:
                            hit_x = (max(self.player.x, fb.x) + min(self.player.x + self.player.w, fb.x + fb.w)) * 0.5
                            hit_y = (max(self.player.y, fb.y) + min(self.player.y + self.player.h, fb.y + fb.h)) * 0.5
                            self.spawn_stage5_boss_hit_effect(hit_x, hit_y, actor=fb)
                        if self.player.invincible_timer <= 0:
                            self.lose_life(); return

            to_remove = []
            for e in self.enemies:
                if not stage9_normal_enemy_section_active(self, e):
                    continue
                env_old_x = float(getattr(e, "x", 0))
                if isinstance(e, ChaserWalker):
                    e.update(self.level, self.TILES_X, self.TILES_Y, self.player)
                elif isinstance(e, Walker):
                    e.update(self.level, self.TILES_X, self.TILES_Y)
                elif isinstance(e, AimShooter):
                    e.update(self.player.x, self.player.y, self.spawn_enemy_bullet)
                elif isinstance(e, Shooter):
                    e.update(self.player.x, self.player.y, self.spawn_enemy_bullet)
                elif isinstance(e, WarpEnemy):
                    e.update(self.level, self.TILES_X, self.TILES_Y, self.player)
                elif isinstance(e, Hopper):
                    e.update(self.level, self.TILES_X, self.TILES_Y)
                elif isinstance(e, MissileEnemy):
                    e.update(self.level, self.TILES_X, self.TILES_Y, self.player)
                elif isinstance(e, Flyer):
                    e.update(self.player)
                else:
                    e.update()

                self.apply_environment_enemy_x(e, env_old_x)
                if not e.alive:
                    to_remove.append(e); continue

                # 未生成ミサイル・未起動フライヤーは当たり判定・踏み判定を行わない
                if isinstance(e, (MissileEnemy, Flyer)) and not getattr(e, "active", True):
                    continue

                if can_stomp(self.player, e, 0.5, 8, 4):
                    # 踏みつけ判定
                    if isinstance(e, StompDamageWalker):
                        # 踏んだ側(プレイヤー)がダメージ
                        if self.player.invincible_timer <= 0:
                            self.lose_life(); return
                    else:
                        stomp_base = 1
                        stomp_dmg  = int(stomp_base * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0))
                        e.damage(stomp_dmg)
                        if e.alive:
                            # 増殖不死フライヤーなど、踏めるが倒れない敵は残す。
                            pass
                        else:
                            to_remove.append(e)
                            play_enemy_defeat_sfx_at(e)
                            self.award_enemy_defeat_score(e)
                        play_sfx_at("STOMP", e.x, e.y, e.w, e.h)
                        self.player.vy = JUMP_VY * 0.6
                else:
                    # ミサイル：爆発中は 32x32 近辺で当たればダメージ
                    if isinstance(e, MissileEnemy):
                        if getattr(e, "explode_timer", 0) > 0:
                            # 爆風判定
                            ex = e.x - 12; ey = e.y - 12; ew = e.w + 24; eh = e.h + 24
                            if aabb(self.player.x, self.player.y, self.player.w, self.player.h, ex, ey, ew, eh):
                                if self.player.invincible_timer <= 0:
                                    self.lose_life(); return
                        else:
                            # 直撃で即爆発
                            if aabb(self.player.x, self.player.y, self.player.w, self.player.h, e.x, e.y, e.w, e.h):
                                e._trigger_explode()
                                if self.player.invincible_timer <= 0:
                                    self.lose_life(); return
                        continue

                    if aabb(self.player.x, self.player.y, self.player.w, self.player.h, e.x, e.y, e.w, e.h):
                        if self.player.invincible_timer <= 0:
                            self.lose_life(); return

            if to_remove:
                for e in to_remove:
                    if e in self.enemies: self.enemies.remove(e)

            for b in list(self.bullets):
                b.update(stage_world_h(self.stage))
                if not b.alive:
                    continue

                # --- タイル衝突(ブロック等)で弾を消す ---
                l, r, t, bty = rect_to_tiles(b.x, b.y, b.w, b.h)
                hit_block = False
                for ty in range(t, bty + 1):
                    for tx in range(l, r + 1):
                        if is_solid_for_bullet(tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty)):
                            hit_block = True
                            break
                    if hit_block:
                        break
                if hit_block:
                    b.alive = False
                    continue
                # -----------------------------------------
                if (self.midboss and self.midboss.alive
                        and normal_stage4_midboss_active(self) and aabb(
                    b.x, b.y, b.w, b.h, self.midboss.x, self.midboss.y, self.midboss.w, self.midboss.h
                )):
                    # Stage9 dedicated midboss: no damage at all before Step1 (15 gems).
                    if self.stage9_midboss_gem_lock_active():
                        play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                        b.alive = False
                        continue
                    # 無敵中の中ボス（例：Stage8ジャンプ中）には弾ダメージを通さない。
                    if getattr(self.midboss, "invincible", False):
                        b.alive = False
                        continue

                    # stage6/9_mid: 通常ショットは無効。Stage9中ボスはさらに跳ね返す。
                    if getattr(self.midboss, "normal_shot_immune", False) and (not self._is_power_bullet(b)):
                        if getattr(self.midboss, "reflect_normal_shot", False):
                            rb = Bullet(b.x, b.y, -float(getattr(b, "vx", 3.0)), power=1, vy=float(getattr(b, "vy", 0.0)))
                            rb.kind = "normal"
                            rb.tag = "midboss_reflect"
                            rb.w = getattr(b, "w", 6)
                            rb.h = getattr(b, "h", 3)
                            rb.max_range = 240
                            self.enemy_bullets.append(rb)
                            play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                        elif (int(getattr(self, "stage", 0)) == 6
                              and bool(getattr(self.midboss, "is_midboss", False))):
                            # 通常Stage6中ボス限定：反射しない防御でも防御音を鳴らす。
                            play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                        b.alive = False
                        continue

                    dmg = b.power * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0)
                    play_sfx_at("BOSS_HIT", self.midboss.x, self.midboss.y, self.midboss.w, self.midboss.h)
                    self.midboss.damage(int(dmg))
                    b.alive = False
                    if not self.midboss.alive:
                        self.start_boss_defeat_effect(self.midboss, was_stage_boss=False)
                        return
                    continue

                # Stage9 TM2マーカー配置のフィールド中ボス/ボスへのショット
                for fb in (list(getattr(self, "field_midbosses", [])) + list(getattr(self, "field_bosses", []))):
                    if not stage9_field_actor_active(self, fb):
                        continue
                    if fb.alive and aabb(b.x, b.y, b.w, b.h, fb.x, fb.y, fb.w, fb.h):
                        # Stage9歴代Stage6ボス限定：通常Stage6と同じく、
                        # プレイヤーショット系は行動状態を問わず常時完全無効。
                        #
                        # 弱点になるのは明示的なWait停止中の「踏みつけ」だけであり、
                        # 通常弾・チャージ弾・ATTACK状態の弾はWait中でも通さない。
                        # field_bosses側の汎用ダメージ処理へ入る前に必ず弾を消し、
                        # 通常Stage6と同じMETAL_REFLECTを鳴らす。
                        is_stage9_stage6_guard_boss = (
                            int(getattr(self, "stage", 0)) == 9
                            and int(getattr(fb, "field_boss_origin_stage", 0) or 0) == 6
                            and not bool(getattr(fb, "is_midboss", False))
                        )
                        if is_stage9_stage6_guard_boss:
                            play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            b.alive = False
                            break

                        if getattr(fb, "invincible", False):
                            b.alive = False
                            break
                        if getattr(fb, "shot_immune_all", False):
                            play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            b.alive = False
                            break
                        if getattr(fb, "normal_shot_immune", False) and (not self._is_power_bullet(b)):
                            if getattr(fb, "reflect_normal_shot", False):
                                rb = Bullet(b.x, b.y, -float(getattr(b, "vx", 3.0)), power=1, vy=float(getattr(b, "vy", 0.0)))
                                rb.kind = "normal"
                                rb.tag = "field_boss_reflect"
                                rb.w = getattr(b, "w", 6)
                                rb.h = getattr(b, "h", 3)
                                rb.max_range = 240
                                self.enemy_bullets.append(rb)
                                play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            elif (int(getattr(self, "stage", 0)) == 9
                                  and bool(getattr(fb, "is_midboss", False))
                                  and int(getattr(fb, "field_boss_origin_stage", 0) or 0) == 6):
                                # Stage9召喚のStage6中ボス限定：反射しない防御でも防御音を鳴らす。
                                play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            b.alive = False
                            break
                        dmg = b.power * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0)
                        play_sfx_at("BOSS_HIT", fb.x, fb.y, fb.w, fb.h)
                        if (int(getattr(self, "stage", 0)) == 9
                                and int(getattr(fb, "field_boss_origin_stage", 0)) == 5
                                and not bool(getattr(fb, "is_midboss", False))):
                            hit_x = clamp(b.x + b.w * 0.5, fb.x, fb.x + fb.w)
                            hit_y = clamp(b.y + b.h * 0.5, fb.y, fb.y + fb.h)
                            self.spawn_stage5_boss_hit_effect(hit_x, hit_y, actor=fb)
                        fb.damage(int(dmg))
                        b.alive = False
                        if not fb.alive:
                            self.start_boss_defeat_effect(fb, was_stage_boss=False)

                        break
                if not b.alive:
                    continue

                for e in self.enemies:
                    if not stage9_normal_enemy_section_active(self, e):
                        continue
                    if isinstance(e, (MissileEnemy, Flyer)) and not getattr(e, "active", True):
                        continue
                    if e.alive and aabb(b.x, b.y, b.w, b.h, e.x, e.y, e.w, e.h):
                        # 通常エネミー「ミサイル」はプレイヤーショットでは爆発・破壊しない。
                        # 通常弾／チャージ弾のどちらもミサイル本体には影響せず、弾だけ消す。
                        # 地形・プレイヤー接触など、従来の爆発条件は変更しない。
                        if isinstance(e, MissileEnemy):
                            b.alive = False
                            break
                        # ワープ敵：通常ショットを反射。パワー弾はダメージ。
                        if isinstance(e, WarpEnemy) and (not self._is_power_bullet(b)):
                            rb = Bullet(b.x, b.y, -float(getattr(b, "vx", 3.0)), power=1, vy=float(getattr(b, "vy", 0.0)))
                            rb.kind = "normal"
                            rb.tag = "warp_reflect"
                            rb.w = getattr(b, "w", 6)
                            rb.h = getattr(b, "h", 3)
                            rb.max_range = 240
                            self.enemy_bullets.append(rb)
                            play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            b.alive = False
                            break
                        # ノーマルショット無効敵：パワー弾のみ有効
                        if isinstance(e, NormalShotImmuneWalker) and (not self._is_power_bullet(b)):
                            play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            b.alive = False
                            break
                        dmg = b.power * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0)
                        e.damage(int(dmg))
                        if not getattr(e, "alive", True):
                            play_enemy_defeat_sfx_at(e)
                            self.award_enemy_defeat_score(e)
                        b.alive = False
                        break

            self.bullets = [b for b in self.bullets if b.alive]

            # === Enemy bullets ===
            for eb in list(self.enemy_bullets):
                eb.update(stage_world_h(self.stage))
                if not eb.alive:
                    continue

                # --- タイル衝突(ブロック等)で敵弾を消す ---
                l, r, t, bty = rect_to_tiles(eb.x, eb.y, eb.w, eb.h)
                hit_block = False
                for ty in range(t, bty + 1):
                    for tx in range(l, r + 1):
                        if is_solid_for_enemy_bullet(tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty)):
                            hit_block = True
                            break
                    if hit_block:
                        break
                if hit_block:
                    if getattr(eb, "pass_tiles", False):
                        pass
                    elif getattr(eb, "tag", None) == "stage3_boss_explosive":
                        eb.trigger_missile_explosion()
                    else:
                        eb.alive = False
                        continue
                # -----------------------------------------

                # ---弾 vs 弾 ---
                self._resolve_bullet_vs_bullet(eb)
                if not eb.alive:
                    continue

                # プレイヤーと当たり判定
                if aabb(eb.x, eb.y, eb.w, eb.h, self.player.x, self.player.y, self.player.w, self.player.h):
                    if getattr(eb, "tag", None) == "stage3_boss_explosive" and getattr(eb, "explode_timer", 0) <= 0:
                        eb.trigger_missile_explosion()
                    if self.player.invincible_timer > 0:
                        # 無敵中は弾だけ消す（好み：消さないなら return だけにしてもOK）
                        if getattr(eb, "tag", None) != "stage3_boss_explosive":
                            eb.alive = False
                        continue

                    eb.alive = False
                    self.lose_life()
                    return

            # 画面外/寿命で整理
            self.enemy_bullets = [eb for eb in self.enemy_bullets if eb.alive]

            if (not getattr(self, "time_limit_disabled", False)
                    and self.time_limit <= 30*60
                    and not self.reaper.active):
                self.reaper.spawn(self.player.x, self.player.y)
                play_sfx("GHOST_APPEAR")
            self.reaper.update(self.player.x, self.player.y)
            if self.reaper.active and aabb(self.player.x, self.player.y, self.player.w, self.player.h,
                                        self.reaper.x, self.reaper.y, self.reaper.w, self.reaper.h):
                if self.player.invincible_timer <= 0:
                    # ゴースト接触時は残り時間を必ず0にしてからミス処理へ移る。
                    # timeover扱いにすることで、復帰後の既存90秒再開仕様は維持する。
                    self.time_limit = 0
                    self.lose_life(kind="timeover"); return

            for it in self.items:
                it.update()
                if it.alive and aabb(self.player.x, self.player.y, self.player.w, self.player.h, it.x, it.y, it.w, it.h):           
                    if it.type == "1UP":
                        play_sfx("ONEUP")
                        self.lives += 1
                    elif it.type == "BIGPTS":
                        play_sfx("COIN")
                        self.add_score(random.randint(300, 1000))
                    elif it.type == "POWER":
                        play_sfx("POWERUP")
                        # ATTACKへ切替（蓄積しない）
                        self.player.pstate = "ATTACK"
                        self.player.armor = 0
                        self.player.try_set_size_keep_bottom_safe(32, 32, self.level, self.TILES_X, self.TILES_Y)
                    elif it.type == "ARMOR":
                        play_sfx("POWERUP")
                        # ARMORへ切替（★蓄積する：最大2回までミス回避）
                        if self.player.pstate != "ARMOR":
                            self.player.pstate = "ARMOR"
                            self.player.try_set_size_keep_bottom_safe(32, 32, self.level, self.TILES_X, self.TILES_Y)
                        # アーマー残量(=回避回数)を+1（上限2）
                        self.player.armor = min(2, max(0, int(getattr(self.player, "armor", 0))) + 1)
                    self.sync_persist_from_player()
                    it.alive = False

            self.items = [i for i in self.items if i.alive]

            # Stage9 gems are stationary, persistent collectibles separate from normal items.
            self._collect_stage9_gems()
            self._update_stage9_midboss_unlock_effect()
            if int(getattr(self, "stage", 0)) == 9 and getattr(self, "stage9_hint_timer", 0) > 0:
                self.stage9_hint_timer -= 1

            self.try_activate_checkpoint()

            if not self.player.alive:
                self.lose_life(); return

            if not getattr(self, "time_limit_disabled", False):
                self.time_limit -= 1
                if self.time_limit <= 0:
                    self.lose_life(kind="timeover"); return

            target = int(self.player.x + self.player.w // 2 - SCREEN_W // 2)
            self.cam_x = clamp(target, 0, WORLD_W - SCREEN_W)

        elif self.scene == "BOSS":
            if self.update_effect_timers():
                return
            if self.update_environment():
                return

            # デバッグプレイ中のみ: ボス部屋でも I キーでプレイヤー無敵ON/OFF。
            # 通常ステージ側と同じ状態を使うので、部屋に入る前/後どちらで切り替えても反映される。
            if self.dev_mode and input_dev_invincible_pressed():
                self.dev_player_invincible = not getattr(self, "dev_player_invincible", False)
                self.screen_notice_text = "DEBUG INVINCIBLE ON" if self.dev_player_invincible else "DEBUG INVINCIBLE OFF"
                self.screen_notice_timer = 0 if self.dev_player_invincible else 60
                if not self.dev_player_invincible and self.player:
                    self.player.invincible_timer = 0

            if self.dev_mode and getattr(self, "dev_player_invincible", False) and self.player:
                self.player.invincible_timer = max(getattr(self.player, "invincible_timer", 0), 999999)

            # --- Boss room summoned enemies (Stage4 boss minions etc.) ---
            to_remove = []
            for e in self.enemies:
                e.update()

                if not e.alive:
                    to_remove.append(e)
                    continue

                if can_stomp(self.player, e, 0.5, 8, 4):
                    stomp_base = 1
                    stomp_dmg  = int(stomp_base * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0))
                    e.damage(stomp_dmg)
                    if not getattr(e, "alive", True):
                        to_remove.append(e)
                        play_enemy_defeat_sfx_at(e)
                        self.award_enemy_defeat_score(e)
                    play_sfx_at("STOMP", e.x, e.y, e.w, e.h)
                    self.player.vy = JUMP_VY * 0.6
                elif aabb(self.player.x, self.player.y, self.player.w, self.player.h, e.x, e.y, e.w, e.h):
                    if self.player.invincible_timer <= 0:
                        self.lose_life(); return

            if to_remove:
                for e in to_remove:
                    if e in self.enemies:
                        self.enemies.remove(e)

            for b in list(self.bullets):
                if not b.alive:
                    continue
                for e in self.enemies:
                    if not stage9_normal_enemy_section_active(self, e):
                        continue
                    if isinstance(e, (MissileEnemy, Flyer)) and not getattr(e, "active", True):
                        continue
                    if e.alive and aabb(b.x, b.y, b.w, b.h, e.x, e.y, e.w, e.h):
                        dmg = b.power * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0)
                        e.damage(int(dmg))
                        if not getattr(e, "alive", True):
                            play_enemy_defeat_sfx_at(e)
                            self.award_enemy_defeat_score(e)
                        b.alive = False
                        break
            self.enemies = [e for e in self.enemies if e.alive]

            # --- Boss FSM tick (config-driven) ---
            if (not getattr(self, "paused", False)) and getattr(self, "boss", None) and getattr(self.boss, "alive", True):
                if getattr(self, "_boss_ai", None):
                    self._boss_ai.update()

            if (getattr(self, "stage", 1) == 2
                and getattr(self, "boss", None)
                and getattr(self.boss, "alive", True)
                and not getattr(self, "paused", False)
                and not getattr(self, "_boss_ai", None)):

                # 着地後の停止タイム(0.5秒)
                if getattr(self, "_s2_land_stop_frames", 0) > 0:
                    self._s2_land_stop_frames -= 1
                    self.boss_stop_timer = max(self.boss_stop_timer, 1)  # 停止維持
                    if self._s2_land_stop_frames == 0:
                        self.boss_stop_timer = 0
                        pcx = self.player.x + getattr(self.player, "w", 16)/2
                        bcx = self.boss.x + getattr(self.boss, "w", 16)/2
                        dir = 1 if pcx >= bcx else -1
                        base = abs(getattr(self, "_s2_walk_speed", getattr(self.boss, "vx", 1.2)))
                        spd = 1.2 if base < 1.2 else base
                        self.boss.vx = spd * dir
                # 事前停止(ジャンプ直前)
                elif getattr(self, "_s2_prejump_frames", 0) > 0:
                    self._s2_prejump_frames -= 1
                    self.boss_stop_timer = max(self.boss_stop_timer, 1)  # 射撃/移動停止
                    if self._s2_prejump_frames == 0:
                        # ジャンプ開始: X/Y 2.0倍でプレイヤー方向へ
                        px = self.player.x + getattr(self.player, "w", 16)/2
                        bx = self.boss.x + getattr(self.boss, "w", 16)/2
                        dir = 1 if px >= bx else -1
                        base_vx = getattr(self.boss, "vx", 1.0)
                        jvx = max(1.0, abs(base_vx)) * 2.0 * dir
                        self.boss.vx = jvx
                        # 縦はプレイヤーのJUMP_VY基準の1.5倍
                        try:
                            jy = JUMP_VY * 2.0
                        except NameError:
                            jy = -9.0 * 2.0
                        self.boss.vy = jy
                        self._s2_in_jump = True
                        # ジャンプ中は射撃不可
                        self._s2_no_shoot_frames = max(self._s2_no_shoot_frames, 45)  # 約0.75秒の射撃禁止(保険)
                        self._s2_walk_speed = max(1.0, abs(base_vx))
                        self.boss_stop_timer = 0
                else:
                    # ジャンプ中の縦運動(簡易物理)
                    if getattr(self, "_s2_in_jump", False):
                        # 重力適用
                        try: g = GRAVITY
                        except NameError: g = 0.5
                        self.boss.vy = getattr(self.boss, "vy", 0.0) + g
                        self.boss.y += self.boss.vy
                        # 着地判定（床Yで止める）
                        floor_y = FLOOR_Y
                        if self.boss.y + getattr(self.boss, "h", 32) >= floor_y:
                            self.boss.y = floor_y - getattr(self.boss, "h", 32)
                            self.boss.vy = 0.0
                            self._s2_in_jump = False
                            # 着地後0.5秒停止
                            self._s2_land_stop_frames = 30
                            self.boss_stop_timer = max(self.boss_stop_timer, 30)
                            # 次の判定までのクールダウンをリセット
                            self._s2_jump_cooldown = 180
                            # 射撃禁止は着地停止中もカバーされるが念のため少し残す
                            self._s2_no_shoot_frames = max(self._s2_no_shoot_frames, 18)
                    else:
                        # 次のジャンプ判定タイマー
                        if getattr(self, "_s2_jump_cooldown", 0) > 0:
                            self._s2_jump_cooldown -= 2
                        else:
                            # 3秒ごとにランダムでジャンプ実行(90%程度)
                            if random.random() < 0.90:
                                # 直前停止フレーム（体感0.35秒）＋射撃禁止
                                self._s2_prejump_frames = 20
                                self._s2_no_shoot_frames = max(self._s2_no_shoot_frames, 20)
                                # 即時停止フラグ（boss_stop_timerと併用、updateは呼ばれない）
                                self.boss_stop_timer = max(self.boss_stop_timer, 20)
                            # 次回判定まで再装填
                            self._s2_jump_cooldown = 180
                # 射撃禁止タイマの減算
                if getattr(self, "_s2_no_shoot_frames", 0) > 0:
                    self._s2_no_shoot_frames -= 1
                # --- Stage2 boss animation state control ---
                if self.stage == 2 and self.boss and self.boss.alive:
                    # ジャンプ中
                    if self._s2_in_jump:
                        self.boss.anim_state = "jump"

                    # 停止中（止まる／着地）
                    elif (
                        self._s2_prejump_frames > 0
                        or self._s2_land_stop_frames > 0
                    ):
                        self.boss.anim_state = "stop"

                    # 歩行中
                    else:
                        self.boss.anim_state = "walk"
            # --- Boss shooting (ステージ1は扇状＋停止＋クールダウン制御) ---
            if getattr(self, "boss", None) and getattr(self.boss, "alive", True):
                # 停止中は発射ロジックを完全停止（連射ループ防止）
                if getattr(self, "boss_stop_timer", 0) > 0:
                    pass
                else:
                    # クールダウン中は弾を撃たない
                    if self.boss_shot_cd > 0:
                        self.boss_shot_cd -= 1
                    else:
                        # Stage3: ボスの射撃は FSM 側（真下ショット）で管理するため、ここでは撃たない
                        if getattr(self, "stage", 1) in (3, 4, 5, 6, 7, 8, 9):
                            # Stage3以降の後半ボスは FSM 側の専用行動で撃つ。横移動中の共通常ショットは出さない。
                            self.boss_shot_cd = max(self.boss_shot_cd, 15)
                        else:
                            bx = int(self.boss.x + getattr(self.boss, "w", 16) // 2)
                            by = int(self.boss.y + getattr(self.boss, "h", 16) // 2)
                            # Stage2: 事前/空中は射撃禁止
                            if getattr(self, "stage", 1) == 2 and getattr(self, "_s2_no_shoot_frames", 0) > 0:
                                # スキップ（クールダウンだけ再設定して暴発防止）
                                self.boss_shot_cd = max(self.boss_shot_cd, 15)

                            if getattr(self, "stage", 1) == 1:
                                # 停止して撃つ（約0.3秒停止）
                                self.boss_stop_timer = 18
                                # 停止前の速度を保存しておき、停止解除時に復元する
                                self._boss_prev_vx = getattr(self.boss, "vx", 0)
                                if hasattr(self.boss, "vx"):
                                    self.boss.vx = 0

                                # プレイヤー方向を基準に扇状ショット（5way）
                                player_cx = self.player.x + getattr(self.player, "w", 16) / 2
                                player_cy = self.player.y + getattr(self.player, "h", 16) / 2
                                base_ang = math.atan2(player_cy - by, player_cx - bx)
                                speed = 2.2
                                for deg in (-20, -10, 0, 10, 20):
                                    rad = base_ang + math.radians(deg)
                                    vx = speed * math.cos(rad)
                                    vy = speed * math.sin(rad)
                                    self.spawn_enemy_bullet(bx, by, vx, vy, tag = "boss")

                                # 次の発射までのクールダウン設定（2秒前後）
                                self.boss_shot_cd = 120
                            else:
                                # 通常ショット（水平）
                                player_center_x = self.player.x + getattr(self.player, "w", 16) / 2
                                dir_vx = 2 if player_center_x >= bx else -2
                                self.spawn_enemy_bullet(bx, by, dir_vx, tag = "boss")
                            self.boss_shot_cd = 60
                            # --- /Boss shooting ---

            if input_pause_pressed():
                self.paused = not self.paused
                if self.paused:
                    self.stop_scene_music()
                else:
                    self.pause_dash_hold_frames = 0
                    self.pause_dash_hold_triggered = False
                    self.update_scene_music(restart=True)
                play_pause_toggle_sfx()
                return
            if self.paused:
                # 追加: CONFIGで「DASH (HOLD)」に割り当てたキー／ボタンを2秒長押し。
                if self._update_pause_dash_hold_to_title():
                    return
                # 既存のタイトル復帰コマンドも維持。
                if input_back_to_title_pressed():
                    self.goto_title()
                    return
                if not input_pause_skip_pressed():
                    return

            for it in self.items: it.update()

            # --- Player shooting (tap = normal / hold->release = charged if powered) ---
            z_now = input_shot_held()

            if self.player.pstate != "ATTACK":
                # 非パワーアップ:押した瞬間に通常弾
                if input_shot_pressed() and self.player.shot_cd == 0:
                    dir_vx = 3 * (1 if self.player.face >= 0 else -1)
                    bx = self.player.x + (self.player.w if dir_vx > 0 else -8)
                    by = self.player.y + self.player.h // 2
                    b = Bullet(bx, by, dir_vx, power = 1)
                    b.kind = "normal"
                    self.bullets.append(b)
                    play_sfx("SHOT")
                    self.player.shot_cd = 10
            else:
                # パワーアップ中:押している間はチャージ
                if z_now and self.player.shot_cd == 0:
                    self.charging = True
                    self.charge_frames = min(self.charge_frames + 1, CHARGE_NEED_FRAMES + 15)

                # 「離した瞬間」= 前フレーム押していた & 今フレーム押していない
                if (not z_now) and self.prev_z and self.player.shot_cd == 0 and self.charging:
                    dir_vx = 3 * (1 if self.player.face >= 0 else -1)
                    bx = self.player.x + (self.player.w if dir_vx > 0 else -8)
                    by = self.player.y + self.player.h // 2

                    if self.charge_frames >= CHARGE_NEED_FRAMES:
                        # === Charged shot ===(X据え置き 6px / Y拡大 30px / センタリング)
                        big = Bullet(bx, by, dir_vx, power = 2)
                        big.kind = "power"
                        big.w = 6
                        big.h = 30
                        big.y = by - big.h // 2 # 完全センタリング
                        self.bullets.append(big)
                        play_sfx("CHARGE_SHOT")
                    else:
                        # 短押し:通常弾
                        b = Bullet(bx, by, dir_vx, power=1)
                        b.kind = "normal"
                        self.bullets.append(b)
                    play_sfx("SHOT")
                    self.player.shot_cd = 10
                    self.charging = False
                    self.charge_frames = 0

            # 最後に prev_z を更新
            self.prev_z = z_now
            # --- /shooting ---

            self.player.update(self.level, self.TILES_X, self.TILES_Y, self.platforms)

            if not self.player.alive and getattr(self.player, "death_cause", "") == "void":
                self.lose_life(kind="void"); return

            if self.boss_left is not None and self.boss_right is not None:
                if self.player.x < self.boss_left:
                    self.player.x = self.boss_left
                    if self.player.vx < 0: self.player.vx = 0
                max_x = self.boss_right - self.player.w
                if self.player.x > max_x:
                    self.player.x = max_x
                    if self.player.vx > 0: self.player.vx = 0

            if self.boss and self.boss.alive:
                if self.boss_stop_timer > 0:
                    self.boss_stop_timer -= 1
                    if hasattr(self.boss, "vx"):
                        self.boss.vx = 0
                    # 停止中: updateを呼ばない
                else:
                    # 停止解除時に元の速度を復元（保存値があれば）
                    if hasattr(self, "_boss_prev_vx") and hasattr(self.boss, "vx"):
                        self.boss.vx = self._boss_prev_vx
                        try:
                            delattr(self, "_boss_prev_vx")
                        except Exception:
                            self._boss_prev_vx = 0
                    self.boss.update(left=WORLD_W - 240, right=WORLD_W - 16)

                                # --- Boss stomp / contact (Stage3: stop中でも踏みダメージが通るように補強) ---
                px, py, pw, ph = int(self.player.x), int(self.player.y), int(self.player.w), int(self.player.h)
                bx, by, bw, bh = int(self.boss.x)-1, int(self.boss.y), int(self.boss.w)+2, int(self.boss.h)+1
                if aabb(px, py, pw, ph, bx, by, bw, bh):
                    # Stage5 boss: プレイヤーがボスへ何らかの形で接触した位置にも爆発演出を出す。
                    # 仕様は変えず、AABBの重なり中央を「接触した部分」として扱う。
                    if int(getattr(self, "stage", 0)) == 5:
                        hit_x = (max(px, bx) + min(px + pw, bx + bw)) * 0.5
                        hit_y = (max(py, by) + min(py + ph, by + bh)) * 0.5
                        self.spawn_stage5_boss_hit_effect(hit_x, hit_y)
                    # デバッグ無敵/通常無敵中は、ボス部屋の接触ミスも無効化する。
                    # 以前はボス部屋側の接触判定だけ player.invincible_timer を見ていなかったため、
                    # 表示上は DEBUG INVINCIBLE ON でも、ボス接触ではミスになっていた。
                    player_hurt_blocked = (getattr(self.player, "invincible_timer", 0) > 0)

                    # 通常の踏み判定 + 追加: 停止中/跳ね返り直後でも上面接触なら踏み扱いにする救済
                    stomp_ok = can_stomp(self.player, self.boss, 0.5, 8, 4)

                    # Stage6 guard boss 専用の安定判定。
                    # ポイント:
                    #   - 「無敵」と「HPが減らない」を分離する。
                    #   - 横移動/扇ショット/ジャンプ前/着地直後は、上から踏めば跳ね返るだけ。
                    #   - HPが減るのは、明示的な Wait 停止中(_stomp_vulnerable=True)だけ。
                    #   - 小ジャンプ中(jump_contact_damage=True)だけ、接触でミス。
                    if getattr(self.boss, "shield_only_stop", False):
                        px_l = self.player.x
                        px_r = self.player.x + self.player.w
                        py_t = self.player.y
                        py_f = self.player.y + self.player.h
                        ex_l = self.boss.x - 8
                        ex_r = self.boss.x + self.boss.w + 8
                        ey_t = self.boss.y
                        ey_top_zone = self.boss.y + self.boss.h * 0.62

                        # can_stomp() は vy>0 必須なので、跳ね返り直後/上に乗った直後に失敗することがある。
                        # Stage6ではそこを「上からの接触」として救済し、横や下からの接触だけミスにする。
                        shield_top_ok = (
                            (px_r > ex_l and px_l < ex_r) and
                            (py_f >= ey_t - 8 and py_f <= ey_top_zone + 6) and
                            (py_t < ey_t + self.boss.h * 0.35)
                        )
                        stomp_ok = stomp_ok or shield_top_ok

                        if getattr(self.boss, "jump_contact_damage", False):
                            if player_hurt_blocked:
                                return
                            self.lose_life(); return

                        if stomp_ok:
                            play_sfx_at("STOMP", self.boss.x, self.boss.y, self.boss.w, self.boss.h)
                            if getattr(self.boss, "_stomp_vulnerable", False):
                                stomp_base = 1
                                stomp_dmg  = int(stomp_base * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0))
                                self.boss.damage(stomp_dmg)
                                if not self.boss.alive:
                                    self.start_boss_defeat_effect(self.boss, was_stage_boss=True)
                                    return
                                self.player.vy = JUMP_VY * 0.7
                            else:
                                # 横移動/扇ショット/小ジャンプ前後:
                                # ダメージ無効を明確にするため、防御音を鳴らして跳ね返す。
                                play_sfx_at("METAL_REFLECT", self.boss.x, self.boss.y, self.boss.w, self.boss.h)
                                self.player.vy = JUMP_VY * 0.55
                            return

                        # 上から踏めていない接触は、通常ボス同様にミス。
                        if player_hurt_blocked:
                            return
                        self.lose_life(); return

                    # 通常ボス側の処理
                    if getattr(self.boss, "invincible", False):
                        if getattr(self.boss, "jump_contact_damage", False):
                            self.lose_life(); return
                        if getattr(self.boss, "stomp_safe_when_invincible", False) and stomp_ok:
                            self.player.vy = JUMP_VY * 0.55
                            return
                        if player_hurt_blocked:
                            return
                        self.lose_life(); return
                    if not stomp_ok and getattr(self.boss, "_stomp_vulnerable", False):
                        # 上から乗っている状態（vyが0でも可）
                        px_l = self.player.x
                        px_r = self.player.x + self.player.w
                        py_f = self.player.y + self.player.h
                        ex_l = self.boss.x - 8
                        ex_r = self.boss.x + self.boss.w + 8
                        ey_t = self.boss.y
                        ey_s = self.boss.y + self.boss.h * 0.5
                        stomp_ok = (px_r > ex_l and px_l < ex_r) and (py_f >= ey_t - 6 and py_f <= ey_s + 6) and (self.player.y < self.boss.y)
                    if stomp_ok:
                        play_sfx_at("STOMP", self.boss.x, self.boss.y, self.boss.w, self.boss.h)
                        if getattr(self.boss, "stomp_damage", False):
                            if player_hurt_blocked:
                                self.player.vy = JUMP_VY * 0.55
                                return
                            self.lose_life(); return
                        stomp_base = 1
                        stomp_dmg  = int(stomp_base * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0))
                        # Stage5の接触爆発はAABB接触時点で出すため、踏み処理側では重複生成しない。
                        self.boss.damage(stomp_dmg)
                        if not self.boss.alive:
                            self.start_boss_defeat_effect(self.boss, was_stage_boss=True)
                            return
                        self.player.vy = JUMP_VY * 0.7
                    else:
                        if player_hurt_blocked:
                            return
                        self.lose_life(); return
            else:
                self.enter_clear_scene()
                return

            for b in list(self.bullets):
                b.update(stage_world_h(self.stage))
                if not b.alive:
                    continue

                # --- タイル衝突(ブロック等)で弾を消す ---
                l, r, t, bty = rect_to_tiles(b.x, b.y, b.w, b.h)
                hit_block = False
                for ty in range(t, bty + 1):
                    for tx in range(l, r + 1):
                        if is_solid_for_bullet(tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty)):
                            hit_block = True
                            break
                        if hit_block: break
                    if hit_block:
                        b.alive = False
                        continue
                    # -----------------------------------------

                    if self.boss and self.boss.alive and aabb(b.x, b.y, b.w, b.h,
                                                              self.boss.x, self.boss.y, self.boss.w, self.boss.h):
                        dmg = (b.power if b.power > 0 else 1) * (ATTACK_MULT_POWERED if self.player.pstate == "ATTACK" else 1.0)
                        # 行動1(上空)は無敵：被弾ダメージを通さない（弾は消す）
                        if getattr(self.boss, "invincible", False):
                            b.alive = False
                            continue
                        # Stage6 boss: 通常/チャージ/ATTACKを問わず、プレイヤーショット系は完全無効。
                        # ショット接触時にも、無効化が分かるよう踏み付け防御時と同じ防御音を鳴らす。
                        if getattr(self.boss, "shot_immune_all", False):
                            play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            b.alive = False
                            continue
                        # Stage6 mid / Stage9 mid など: 通常ショットのみ無効。チャージ/ATTACK弾は通す。
                        if getattr(self.boss, "normal_shot_immune", False) and (not self._is_power_bullet(b)):
                            if getattr(self.boss, "reflect_normal_shot", False):
                                b.vx = -float(getattr(b, "vx", 0.0))
                                b.vy = -float(getattr(b, "vy", 0.0))
                                b.tag = "boss_reflect"
                                play_sfx_at("METAL_REFLECT", b.x, b.y, b.w, b.h)
                            else:
                                b.alive = False
                            continue
                        play_sfx_at("BOSS_HIT", self.boss.x, self.boss.y, self.boss.w, self.boss.h)
                        if int(getattr(self, "stage", 0)) == 5:
                            hit_x = clamp(b.x + b.w * 0.5, self.boss.x, self.boss.x + self.boss.w)
                            hit_y = clamp(b.y + b.h * 0.5, self.boss.y, self.boss.y + self.boss.h)
                            self.spawn_stage5_boss_hit_effect(hit_x, hit_y)
                        self.boss.damage(int(dmg))
                        b.alive = False
                        if not self.boss.alive:
                            self.start_boss_defeat_effect(self.boss, was_stage_boss=True)
                            return
                self.bullets = [b for b in self.bullets if b.alive]

            # === Enemy bullets (boss scene, for future shooters etc.) ===
            for eb in list(self.enemy_bullets):
                eb.update(stage_world_h(self.stage))
                if not eb.alive:
                    continue

                # --- タイル衝突(ブロック等)で敵弾を消す---
                l, r, t, bty = rect_to_tiles(eb.x, eb.y, eb.w, eb.h)
                hit_block = False
                for ty in range(t, bty + 1):
                    for tx in range(l, r + 1):
                        if is_solid_for_enemy_bullet(tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty)):
                            hit_block = True
                            break
                    if hit_block:
                        break
                if hit_block:
                    if getattr(eb, "tag", None) == "stage3_boss_explosive":
                        eb.trigger_missile_explosion()
                    else:
                        eb.alive = False
                        continue
                # ----------------------------------------

                # ---弾 vs 弾 ---
                self._resolve_bullet_vs_bullet(eb)
                if not eb.alive:
                    continue
                # ---プレイヤーとの当たり ---
                if aabb(eb.x, eb.y, eb.w, eb.h, self.player.x, self.player.y, self.player.w, self.player.h):
                    if getattr(eb, "tag", None) == "stage3_boss_explosive" and getattr(eb, "explode_timer", 0) <= 0:
                        eb.trigger_missile_explosion()
                    if self.player.invincible_timer > 0:
                        if getattr(eb, "tag", None) != "stage3_boss_explosive":
                            eb.alive = False
                        continue
                    eb.alive = False
                    self.lose_life()
                    return
                
            self.enemy_bullets = [eb for eb in self.enemy_bullets if eb.alive]
            self.bullets = [b for b in self.bullets if b.alive]

            if not getattr(self, "time_limit_disabled", False):
                self.time_limit -= 1
                if self.time_limit <= 0:
                    self.lose_life(kind="timeover"); return

            self.cam_x = clamp(WORLD_W - SCREEN_W, 0, WORLD_W - SCREEN_W)

        elif self.scene == "CLEAR":
            # ※旧:ステージ5での隠し解放は廃止
            if input_decide_pressed():
                self.sync_persist_from_player()

                # ステージ8クリア時、10万点以上または到達済みならステージ9へ。
                if self.stage == 8:
                    if self.stage9_reached or self.score >= Game.STAGE9_UNLOCK_SCORE:
                        # 一度到達した進入権は、以後のコンテニュー後も保持する。
                        self.stage9_reached = True
                        self.clear_music_name = None
                        self.stage = 9
                        self.reset_stage(full_reset=True)
                        self.scene = "PLAY"
                    else:
                        # 未達ならタイトルへ戻る(コンティニューなどはタイトルで)
                        self.goto_title()

                # 通常の連番進行(1〜7、9→タイトル)
                elif self.stage < self.max_stage:
                    self.clear_music_name = None
                    self.stage += 1
                    self.reset_stage(full_reset=True)
                    self.scene = "PLAY"
                else:
                    # 9 クリア後などはタイトルへ
                    self.clear_music_name = None
                    self.goto_title()

        elif self.scene == "GAMEOVER":
            if input_decide_pressed():
                self.stop_scene_music()
                self.scene = "TITLE"

    def spawn_stage5_boss_hit_effect(self, hit_x, hit_y, frames=12, actor=None):
        """Stage5ボス命中位置に IMAGE0 (64,112) の16x16爆発を出す（見た目のみ）。

        通常Stage5に加え、Stage9通常フィールドに再配置された歴代Stage5ボスだけを許可する。
        他ステージ・他ボスの仕様には影響させない。
        """
        current_stage = int(getattr(self, "stage", 0))
        normal_stage5 = (current_stage == 5)
        stage9_field_stage5 = (
            current_stage == 9
            and actor is not None
            and int(getattr(actor, "field_boss_origin_stage", 0)) == 5
            and not bool(getattr(actor, "is_midboss", False))
        )
        if not (normal_stage5 or stage9_field_stage5):
            return
        self.stage5_boss_hit_effects.append([float(hit_x) - 8, float(hit_y) - 8, max(1, int(frames))])

    def draw_stage5_boss_hit_effects(self):
        """Stage5ボスの踏み/ショット命中爆発をワールド座標で描画。"""
        effects = getattr(self, "stage5_boss_hit_effects", [])
        if not effects:
            return
        alive = []
        for fx in effects:
            x, y, timer = fx
            if timer <= 0:
                continue
            # IMAGE0 (64,112): 16x16爆発。短時間表示のみでゲーム仕様には影響しない。
            pyxel.blt(int(x), int(y), 0, 64, 112, 16, 16, 0)
            timer -= 1
            if timer > 0:
                alive.append([x, y, timer])
        self.stage5_boss_hit_effects = alive

    def draw_player_with_effect(self):
        """プレイヤーのミス/アーマー点滅を含め、全場面で暗い輪郭影を追加。"""

        def draw_with_outline(draw_at):
            """実座標を変えず、上下左右1pxに黒いシルエットを描いて輪郭を作る。"""
            if True:
                try:
                    for col in range(1, 16):
                        pyxel.pal(col, 0)
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        draw_at(dx, dy)
                finally:
                    pyxel.pal()
            draw_at(0, 0)

        # 通常/ATTACKミス中：IMAGE0 (64,144) の16x16ミス絵を早点滅表示。
        if getattr(self, "player_miss_timer", 0) > 0:
            if (self.player_miss_timer // 4) % 2 == 0:
                def draw_miss(dx, dy):
                    x = int(self.player.x) + dx
                    y = int(self.player.y) + dy
                    if self.player.face >= 0:
                        pyxel.blt(x, y, 0, 64, 144, 16, 16, 0)
                    else:
                        pyxel.blt(x, y, 0, 64, 144, -16, 16, 0)
                draw_with_outline(draw_miss)
            return

        # ARMOR被弾後：減った後の状態の描画を早点滅表示。
        if getattr(self, "armor_break_timer", 0) > 0:
            if (self.armor_break_timer // 4) % 2 == 0:
                spr = getattr(self, "armor_break_spr", "PLAYER")
                w = 32 if spr.startswith("PLAYER_ARMOR") else 16
                h = 32 if spr.startswith("PLAYER_ARMOR") else 16
                def draw_armor_break(dx, dy):
                    draw_char_sprite(spr, self.player.x + dx, self.player.y + dy,
                                     w, h, self.player.face, 0)
                draw_with_outline(draw_armor_break)
            return

        def draw_normal(dx, dy):
            if dx == 0 and dy == 0:
                self.player.draw()
                return
            old_x, old_y = self.player.x, self.player.y
            try:
                self.player.x = old_x + dx
                self.player.y = old_y + dy
                self.player.draw()
            finally:
                self.player.x, self.player.y = old_x, old_y

        draw_with_outline(draw_normal)

        # 視界演出や環境文字とは分離。実座標・当たり判定・操作には影響しない。

    def draw_shadow_text(self, x, y, text, col=7, shadow_col=0):
        """文字を1px右下の影付きで描画（視認性向上）。"""
        pyxel.text(x + 1, y + 1, text, shadow_col)
        pyxel.text(x, y, text, col)

    def draw_screen_notice(self):
        """MISS / RETRY などの中央メッセージ表示。"""
        text = getattr(self, "screen_notice_text", "")
        if not text:
            return

        # 中央に読みやすく表示。背景帯を敷いて視認性を上げる。
        w = len(text) * 4
        x = SCREEN_W // 2 - w // 2
        y = 104
        pyxel.rect(x - 8, y - 6, w + 16, 18, 0)
        pyxel.rectb(x - 8, y - 6, w + 16, 18, 7)
        self.draw_shadow_text(x, y, text, 8 if text == "MISS" else 11)

    def draw_midboss_explosion_effect(self):
        """Stage4中ボス自爆：通常ミサイル爆発スプライトを流用して描画。"""
        if getattr(self, "midboss_explosion_timer", 0) <= 0:
            return

        # 点滅させず、短時間だけ2x2で爆発を見せる。
        x = int(getattr(self, "midboss_explosion_x", 0))
        y = int(getattr(self, "midboss_explosion_y", 0))
        w = max(16, int(getattr(self, "midboss_explosion_w", 32)))
        h = max(16, int(getattr(self, "midboss_explosion_h", 32)))
        for yy in range(y, y + h, 16):
            for xx in range(x, x + w, 16):
                draw_char_sprite("MISSILE_L_EXP", xx, yy, 16, 16, face=1, frame=0)

    def draw_defeated_boss_effect(self, was_stage_boss=False):
        """中ボス/ボス撃破時、現在の描画を使って早点滅しながら消す。"""
        if getattr(self, "boss_defeat_timer", 0) <= 0:
            return
        if bool(getattr(self, "defeated_boss_was_stage_boss", False)) != bool(was_stage_boss):
            return
        b = getattr(self, "defeated_boss", None)
        if b is None:
            return

        # 早点滅。後半ほど表示される頻度が減り、霞むように消える。
        t = self.boss_defeat_timer
        total = self.BOSS_DEFEAT_FRAMES
        if t > total * 2 // 3:
            visible = (t // 4) % 2 == 0
        elif t > total // 3:
            visible = (t // 3) % 2 == 0
        else:
            visible = (t // 2) % 3 == 0

        if visible:
            b.draw()

        # 撃破時の追加爆発演出（見た目のみ）。
        # 既存の点滅はそのまま維持し、IMAGE0 (64,112) の16x16爆発を
        # ボス/中ボス本体の上に時間差で重ねる。
        self.draw_defeated_boss_explosions(b, t, total)

    def draw_defeated_boss_explosions(self, boss_obj, timer, total):
        """中ボス/ボス撃破中、ボディ各所に小爆発を重ねて描画する。"""
        if boss_obj is None:
            return

        try:
            progress = max(0, int(total) - int(timer))
            x = float(getattr(boss_obj, "x", 0))
            y = float(getattr(boss_obj, "y", 0))
            w = max(16, int(getattr(boss_obj, "w", 32)))
            h = max(16, int(getattr(boss_obj, "h", 32)))

            # サイズに応じて爆発数を増やす。中ボスは控えめ、ボスは多め。
            count = max(3, min(10, (w * h) // 512 + 2))
            for i in range(count):
                start = i * 6
                life = 22
                if progress < start or progress >= start + life:
                    continue

                # ランダムを使わず、毎回同じ位置に出す（再現性重視）。
                span_x = max(1, w - 16)
                span_y = max(1, h - 16)
                ox = (i * 23 + (i % 3) * 7) % span_x
                oy = (i * 17 + (i % 2) * 11) % span_y

                # 後半は少し揺らして、爆発が広がる感じにする。
                pulse = (progress - start) // 4
                draw_x = int(x + ox - 2 + (pulse % 3))
                draw_y = int(y + oy - 2 + ((pulse + i) % 3))
                pyxel.blt(draw_x, draw_y, 0, 64, 112, 16, 16, 0)
        except Exception:
            pass

    def draw_stage_normal_background_effects(self, include_during_environment=True):
        """Stage1〜8の通常背景へ、描画専用の控えめな演出を追加する。

        TM0の直後、TM1・キャラクターより前に描くため、当たり判定・物理・
        敵やプレイヤーの機能には一切影響しない。
        include_during_environment=False: 環境変化中は従来背景を優先。
        include_during_environment=True : 環境変化中も本演出を残す。
        """
        stage = int(getattr(self, "stage", 0) or 0)
        if stage not in range(1, 9):
            return
        if not include_during_environment and getattr(self, "environment", "NONE") != "NONE":
            return

        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        top = cam_y
        bottom = cam_y + SCREEN_H
        left = cam_x
        frame = int(pyxel.frame_count)

        try:
            # Stage1: 上方ほど濃紺。現在の背景を残し、薄い帯を重ねる。
            if stage == 1:
                bands = ((0, 10, 0.25), (10, 20, 0.17), (20, 30, 0.09))
                for y1, y2, alpha in bands:
                    pyxel.dither(alpha)
                    pyxel.rect(left, top + y1, SCREEN_W, y2 - y1, 1)

            # Stage2: 上空を水色から濃紺へ。薄い星をまばらに配置。
            elif stage == 2:
                bands = ((0, 24, 1, 0.34), (24, 50, 1, 0.23),
                         (50, 78, 5, 0.14), (78, 106, 12, 0.08))
                for y1, y2, col, alpha in bands:
                    pyxel.dither(alpha)
                    pyxel.rect(left, top + y1, SCREEN_W, y2 - y1, col)
                # 濃紺部でも埋もれないよう、星は少し明るく・やや多めにする。
                pyxel.dither(0.72)
                for i in range(22):
                    seed = i * 97 + 31
                    sx = (seed * 7) % SCREEN_W
                    sy = 5 + (seed * 11) % 72
                    # ゆっくり明滅しつつ、消えている時間を短くする。
                    if ((frame // 30 + i * 3) % 12) == 11:
                        continue
                    col = 7 if i % 4 else 10
                    wx, wy = left + sx, top + sy
                    pyxel.pset(wx, wy, col)
                    if i % 6 == 0 and ((frame // 18 + i) % 3) != 0:
                        pyxel.pset(wx - 1, wy, col)
                        pyxel.pset(wx + 1, wy, col)

            # Stage3: 画面下部に薄い砂埃。視認性を損なわない低密度。
            elif stage == 3:
                for offset, alpha in ((208, 0.05), (220, 0.08), (232, 0.12), (244, 0.17)):
                    pyxel.dither(alpha)
                    pyxel.rect(left, top + offset, SCREEN_W, SCREEN_H - offset, 9)
                pyxel.dither(0.23)
                drift = frame // 6
                for i in range(16):
                    seed = i * 83 + 17
                    sx = (seed * 5 + drift * (1 + i % 2)) % (SCREEN_W + 20) - 10
                    sy = 210 + (seed * 13) % 43
                    pyxel.pset(left + sx, top + sy, 10 if i % 3 else 9)

            # Stage4・7: 画面全体へ、控えめなダイヤモンドダスト。
            elif stage in (4, 7):
                pyxel.dither(0.28)
                count = 18 if stage == 4 else 22
                for i in range(count):
                    seed = i * 71 + stage * 41
                    sx = (seed * 9 + frame // (10 + i % 5)) % SCREEN_W
                    sy = (seed * 13 + frame // (18 + i % 7)) % SCREEN_H
                    phase = (frame // 12 + i * 5) % 16
                    if phase not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
                        continue
                    col = 7 if i % 5 else 12
                    wx, wy = left + sx, top + sy
                    pyxel.pset(wx, wy, col)
                    if phase in (2, 3, 4) and i % 4 == 0:
                        pyxel.pset(wx - 1, wy, col)
                        pyxel.pset(wx + 1, wy, col)
                        pyxel.pset(wx, wy - 1, col)
                        pyxel.pset(wx, wy + 1, col)

            # Stage5・8: プレイヤーの向いている側の斜め上に小さな松明。
            elif stage in (5, 8):
                # 火事環境では周囲の炎表現を優先し、松明は表示しない。
                if getattr(self, "environment", "NONE") == "FIRE":
                    return
                player = getattr(self, "player", None)
                if player is not None:
                    face = 1 if int(getattr(player, "face", 1)) >= 0 else -1
                    pw = int(getattr(player, "w", 16))
                    px = int(getattr(player, "x", 0))
                    py = int(getattr(player, "y", 0))
                    tx = px + (pw + 18 if face > 0 else -18)
                    ty = py - 22
                    flicker = (frame // 4) % 3
                    # 壁掛け金具と柄。
                    pyxel.dither(0.72)
                    pyxel.line(tx, ty + 7, tx, ty + 16, 4)
                    pyxel.line(tx, ty + 13, tx - face * 4, ty + 16, 4)
                    # 炎の淡い光。背景層なので敵やプレイヤーを覆わない。
                    pyxel.dither(0.07)
                    pyxel.circ(tx, ty + 2, 18 + flicker, 10)
                    pyxel.dither(0.13)
                    pyxel.circ(tx, ty + 2, 10 + flicker, 9)
                    pyxel.dither(0.72)
                    pyxel.circ(tx, ty + 3, 3, 9)
                    pyxel.circ(tx, ty + 1 - flicker, 2, 10)
                    pyxel.pset(tx, ty - 2 - flicker, 7)

            # Stage6: 下方へ淡いピンクのグラデーション。
            elif stage == 6:
                bands = ((208, 220, 0.05), (220, 232, 0.09),
                         (232, 244, 0.14), (244, 256, 0.20))
                for y1, y2, alpha in bands:
                    pyxel.dither(alpha)
                    pyxel.rect(left, top + y1, SCREEN_W, y2 - y1, 14)
        finally:
            pyxel.dither(1.0)

    def draw_environment_visible_diamond_dust(self):
        """Stage4・7の環境変化中だけ、環境色フィルターより手前で消えた
        ダイヤモンドダストを背景最前面へ描き直す。描画専用。
        """
        stage = int(getattr(self, "stage", 0) or 0)
        if stage not in (4, 7) or getattr(self, "environment", "NONE") == "NONE":
            return
        left = int(getattr(self, "cam_x", 0))
        top = int(getattr(self, "cam_y", 0))
        frame = int(pyxel.frame_count)
        try:
            pyxel.dither(0.34)
            count = 18 if stage == 4 else 22
            for i in range(count):
                seed = i * 71 + stage * 41
                sx = (seed * 9 + frame // (10 + i % 5)) % SCREEN_W
                sy = (seed * 13 + frame // (18 + i % 7)) % SCREEN_H
                phase = (frame // 12 + i * 5) % 16
                if phase not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
                    continue
                col = 7 if i % 5 else 12
                wx, wy = left + sx, top + sy
                pyxel.pset(wx, wy, col)
                if phase in (2, 3, 4) and i % 4 == 0:
                    pyxel.pset(wx - 1, wy, col)
                    pyxel.pset(wx + 1, wy, col)
                    pyxel.pset(wx, wy - 1, col)
                    pyxel.pset(wx, wy + 1, col)
        finally:
            pyxel.dither(1.0)

    def draw_stage9_normal_background_filter(self, draw_w, draw_h):
        """Stage9通常時のみ、プレイヤー中心の薄いプリズム状グラデーションを描く。

        従来の四隅固定フィルターはいったん撤廃し、プレイヤーを中心とした
        大きな同心円リングの一部だけが画面四隅へ見える構成にする。
        中央の完全可視範囲は維持し、背景・当たり判定・操作には影響しない。
        """
        if int(getattr(self, "stage", 0)) != 9:
            return
        if getattr(self, "environment", "NONE") != "NONE":
            return

        player = getattr(self, "player", None)
        if player is None:
            return

        # プレイヤーの画面上の中心を基準にする。
        cx = int(getattr(player, "x", 0) + getattr(player, "w", 16) * 0.5)
        cy = int(getattr(player, "y", 0) + getattr(player, "h", 16) * 0.5)

        # 中央は完全可視。遠方へ行くほど虹色の弧が重なる。
        # circbのみを使うため、画面中央を塗りつぶさず四隅側にだけ現れる。
        # Pyxelのditherは極端に小さい値（約0.06未満）では、
        # パターン上ほぼ1画素も描かれず消えて見える。
        # 透明感を保ちつつ確実に見える段階へ引き上げる。
        prism_bands = (
            (112, 2, 0.08),   # 紫
            (121, 5, 0.09),   # 青
            (130, 12, 0.10),  # 水色
            (139, 11, 0.11),  # 緑
            (148, 10, 0.12),  # 黄
            (157, 9, 0.11),   # 橙
            (166, 8, 0.10),   # 赤
            (175, 2, 0.075),  # 外側に薄い紫の余韻
        )

        try:
            # 各色を帯状に重ねる。中央側は細く、四隅側ほど少し広げて
            # 虹色の線ではなく、薄いプリズムのグラデーションに見せる。
            for band_index, (radius, color, alpha) in enumerate(prism_bands):
                pyxel.dither(alpha)
                half_width = 4 if band_index < 2 else 5
                for spread in range(-half_width, half_width + 1):
                    pyxel.circb(cx, cy, radius + spread, color)
        finally:
            pyxel.dither(1.0)

    def draw_stage9_upward_rain_background(self):
        """Stage9専用。下から上へゆっくり流れる微細な背景粒子。

        環境変化のRAINとは完全に独立し、環境状態・移動・当たり判定を変更しない。
        TM0の後、TM1より前に描画するため、背景演出としてのみ見える。
        """
        if int(getattr(self, "stage", 0)) != 9:
            return

        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        spacing = 18
        count = SCREEN_W // spacing + 5

        try:
            pyxel.dither(0.38)
            for i in range(count):
                seed = i * 53 + 19
                screen_x = (i * spacing + (seed % 13) + (frame // 18) % 7) % (SCREEN_W + 16) - 8
                # 環境雨（毎フレーム2px下降）よりかなり遅い、約3フレームで1px上昇。
                screen_y = (seed * 9 - frame // 3) % (SCREEN_H + 24) - 12
                length = 2 + (seed % 3)
                col = 5 if seed % 4 else 6
                wx = cam_x + screen_x
                wy = cam_y + screen_y
                pyxel.line(wx, wy, wx, wy + length, col)
        finally:
            pyxel.dither(1.0)

    def draw_stage9_alarm_lights_background(self):
        """Stage9専用。同じ場所で数回素早く点滅後、別配置へ移る警報灯。"""
        if int(getattr(self, "stage", 0)) != 9:
            return

        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        # BOSS描画では pyxel.camera(cam_x, 0) を使うため、通常フィールドの
        # cam_yを足すと警報灯が画面外へ描かれてしまう。
        cam_y = 0 if getattr(self, "scene", "") == "BOSS" else int(getattr(self, "cam_y", 0))

        # 約4秒間は同じ場所・個数を維持し、その間に短い点滅を繰り返す。
        epoch_len = 240
        epoch = frame // epoch_len
        local = frame % epoch_len
        base = (epoch * 1103515245 + 12345) & 0x7fffffff
        count = 1 + ((base >> 5) % 4)

        # 1回約0.55秒の点滅。短い休止を挟み、同じ位置で5回程度繰り返す。
        pulse_len = 34
        active_span = 27

        try:
            for i in range(count):
                h = (base ^ ((i + 1) * 2654435761)) & 0xffffffff
                sx = 14 + (h % max(1, SCREEN_W - 28))
                sy = 18 + ((h >> 9) % max(1, SCREEN_H - 36))
                center_r = 1 + ((h >> 18) % 2)
                middle_r = center_r + 3 + ((h >> 20) % 2)
                outer_r = middle_r + 4 + ((h >> 22) % 3)

                # 各ライトの開始だけ少しずらすが、epoch中の位置は固定。
                offset = ((h >> 12) % 18) + i * 3
                shifted = local - offset
                if shifted < 0:
                    continue

                pulse_index = shifted // pulse_len
                phase = shifted % pulse_len
                if pulse_index >= 6 or phase >= active_span:
                    continue

                # 従来より速い展開：中心→中間→外周、中心から順に消える。
                show_center = phase < 16
                show_middle = 4 <= phase < 21
                show_outer = 8 <= phase < 27

                wx = cam_x + sx
                wy = cam_y + sy

                if show_outer:
                    pyxel.dither(0.10)
                    pyxel.circ(wx, wy, outer_r, 8)
                if show_middle:
                    pyxel.dither(0.18)
                    pyxel.circ(wx, wy, middle_r, 8)
                if show_center:
                    pyxel.dither(0.34)
                    pyxel.circ(wx, wy, center_r, 8)
        finally:
            pyxel.dither(1.0)

    def draw_stage9_final_boss_backdrop(self):
        """Stage9通常背景と同じ、下から上へ流れる星をラスボス部屋にも描く。"""
        if int(getattr(self, "stage", 0)) != 9 or getattr(self, "scene", "") != "BOSS":
            return
        left = int(getattr(self, "boss_left", WORLD_W - 240))
        right = int(getattr(self, "boss_right", WORLD_W - 16))
        frame = int(pyxel.frame_count)
        width = max(1, right - left)

        # Stage9通常背景の印象を維持した、下から上へ流れる星。
        # 画面座標ではなくボス部屋のワールド座標へ描く。
        for i in range(38):
            seed = i * 97 + 29
            x = left + 3 + ((seed * 11) % max(1, width - 6))
            speed_div = 2 + (i % 4)
            y = FLOOR_Y - ((frame // speed_div + seed * 7) % (FLOOR_Y + 24))
            col = (7, 10, 12)[i % 3]
            pyxel.pset(x, y, col)
            if i % 7 == 0:
                pyxel.pset(x, y + 1, col)

    def draw_stage9_final_boss_floor_overlay(self):
        """ラスボス部屋の表示領域全幅・画面下端まで床を最終上書きする。"""
        if int(getattr(self, "stage", 0)) != 9 or getattr(self, "scene", "") != "BOSS":
            return

        # boss_right は部屋右端より16px内側になる構成があり、それを基準にすると
        # 画面右下に1タイル分の欠けが残る。実際のカメラ表示領域を基準に埋める。
        view_left = int(getattr(self, "cam_x", getattr(self, "boss_left", WORLD_W - SCREEN_W)))
        view_right = view_left + SCREEN_W
        tile_left = (view_left // TILE) * TILE
        tile_right = ((view_right + TILE - 1) // TILE) * TILE

        # FLOOR_Yから画面下端までを背景色で塞いだ後、GROUNDを複数段敷く。
        # これによりTM1・移動床・部屋境界由来の縦長の欠けも残らない。
        floor_bottom = max(FLOOR_Y + TILE, SCREEN_H)
        pyxel.rect(tile_left, FLOOR_Y, max(TILE, tile_right - tile_left), floor_bottom - FLOOR_Y, 0)
        for y in range(FLOOR_Y, floor_bottom, TILE):
            for x in range(tile_left, tile_right, TILE):
                draw_platform_span(x, y, TILE, TILE, "GROUND")

    def draw_stage9_boss_door_shimmer(self):
        """Stage9のボス扉だけを、全体に波が通るように揺らして再描画する（描画専用）。"""
        if int(getattr(self, "stage", 0)) != 9:
            return
        if getattr(self, "scene", "") != "PLAY":
            return

        anchors = list(getattr(self, "_boss_door_anchors", []))
        if not anchors:
            # ミス後の再読み込みでアンカー再検出に失敗しても、
            # _apply_stage9_door_gate が保持している座標からゆらめきを継続する。
            anchors = list(getattr(self, "stage9_door_tiles", set()))
        if not anchors:
            return

        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        frame = int(pyxel.frame_count)
        u0, v0 = TILES["BOSS_DOOR"]

        for tx, ty in anchors:
            # 実際に扉判定が有効な時だけ描画する。
            # Stage9中ボス撃破前の非表示状態や、通常の出現条件には影響させない。
            if tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty) != TILE_DOOR:
                continue

            x = int(tx * TILE)
            y = int(ty * TILE)

            # 画面外の扉は描画しない。
            if x + 34 < cam_x or x - 2 > cam_x + SCREEN_W:
                continue
            if y + 34 < cam_y or y - 2 > cam_y + SCREEN_H:
                continue

            # 32x32の扉を2pxずつの横帯に分割し、帯ごとに位相をずらす。
            # 元のTM1描画の上から重ねるだけなので、当たり判定・座標・扉機能は不変。
            whole_sway = math.sin(frame * 0.055) * 0.65
            for sy in range(0, 32, 2):
                wave = (
                    math.sin(frame * 0.13 + sy * 0.42) * 1.25
                    + math.sin(frame * 0.047 - sy * 0.21) * 0.55
                    + whole_sway
                )
                shift_x = int(round(wave))
                pyxel.blt(
                    x + shift_x,
                    y + sy,
                    0,
                    u0,
                    v0 + sy,
                    32,
                    2,
                    0,
                )

    def draw_level(self):
        # カメラは外側で適用済み

        # --- tilemap 0 (background) image source ---
        try:
            pyxel.tilemaps[0].imgsrc = 0
        except AttributeError:
            pyxel.tilemaps[0].reftimg = 0

        stage_index = tilemap_stage_index(self.stage)
        v_row = stage_index * 256  # 8px基準（32セル × 8px）

        # 背景（TM0）
        draw_h = stage_world_h(self.stage)

        # 重力異常中だけ、TM0背景に描画専用の微細な揺れを加える。
        # TM1・キャラクター・当たり判定・ゲーム座標には一切影響しない。
        bg_float_y = 0
        current_env = getattr(self, "environment", "NONE")
        if current_env == "GRAVITY_ANOMALY":
            bg_float_y = int(round(math.sin(pyxel.frame_count * 0.035)))
        elif current_env == "HIGH_GRAVITY":
            # 約2.6秒ごとに数フレームだけ、背景を1px下へ沈ませる。
            # 空間全体に一瞬「ズン」と重圧が掛かる印象を作る描画のみの処理。
            bg_float_y = self.high_gravity_pressure_offset()
        pyxel.bltm(0, bg_float_y, 0, 0, v_row, 144 * TILE, draw_h, 0)

        self.draw_stage_normal_background_effects()

        # Stage9通常時だけ、TM0背景を黒基調＋プレイヤーから離れるほど
        # 紫が濃くなる透明フィルターにする。環境変化中は従来描画のまま。
        self.draw_stage9_normal_background_filter(144 * TILE, draw_h)

        # 低重力／高重力：TM0背景だけに、ごく薄い青白い色調を重ねる。
        # 高重力も背景の基調は低重力と共通にし、粒子方向と黒線で差別化する。
        if getattr(self, "environment", "NONE") in ("GRAVITY_ANOMALY", "HIGH_GRAVITY"):
            try:
                pyxel.dither(0.20)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 12)
                pyxel.dither(0.08)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 7)
            finally:
                pyxel.dither(1.0)

        # 雨環境時は「背景だけ」を少し暗くする。
        # この時点ではTM1（ブロック類）をまだ描いていないため、
        # ブロック・キャラクター・ショットの色には影響しない。
        if getattr(self, "environment", "NONE") == "RAIN":
            try:
                pyxel.dither(0.28)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 0)
            finally:
                pyxel.dither(1.0)

        # 雪環境時は「背景だけ」に灰色の薄い色調を重ねる。
        # TM1（ブロック類）より前なので、ブロック・キャラクター・ショットは変色しない。
        if getattr(self, "environment", "NONE") == "SNOW":
            try:
                pyxel.dither(0.34)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 13)
            finally:
                pyxel.dither(1.0)

        # 霧：TM0背景だけを少し白っぽくする。
        # TM1やキャラクターより前なので、それらの元色は維持される。
        if getattr(self, "environment", "NONE") == "FOG":
            try:
                pyxel.dither(0.24)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 7)
            finally:
                pyxel.dither(1.0)

        # 酷暑：TM0背景へ、明確なオレンジ色を重ねる。
        if getattr(self, "environment", "NONE") == "HEAT":
            try:
                pyxel.dither(0.48)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 9)
            finally:
                pyxel.dither(1.0)
            self.draw_heat_haze_background(v_row, draw_h)

        # 火事：TM0背景をかなり赤くし、酷暑と同系統の蜃気楼をより強く描く。
        # TM1より前なので、ブロック・敵・プレイヤー等の色は維持される。
        if getattr(self, "environment", "NONE") == "FIRE":
            try:
                pyxel.dither(0.68)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 8)
                pyxel.dither(0.26)
                pyxel.rect(0, 0, 144 * TILE, draw_h, 9)
            finally:
                pyxel.dither(1.0)
            self.draw_heat_haze_background(v_row, draw_h)

        # Stage4・7は環境色フィルター後にもダイヤモンドダストを描き、
        # 雨・雪などの環境変化中でも見えるようにする。
        self.draw_environment_visible_diamond_dust()

        # Stage9固有の背景演出。環境雨とは独立した上昇粒子と、
        # ランダムな位置・数・間隔で明滅する薄い警報ライト。
        self.draw_stage9_upward_rain_background()
        self.draw_stage9_alarm_lights_background()

        # --- TM1 (variable/interactive) ---
        try:
            TM_VAR = pyxel.tilemaps[1]
            try:
                TM_VAR.imgsrc = 0
            except AttributeError:
                TM_VAR.reftimg = 0
        except Exception:
            TM_VAR = None

        # TM1 が無い環境ではここで終了（ゲーム自体は成立する）
        if TM_VAR is None:
            return

        # ========== AUTO（TILE_GHOST）の点滅を TM1 書き換えで表現 ==========
        # TM1 は 8px タイルマップとして扱っている（16px タイル = 2x2 セル）
        v8_row = stage_index * 32  # 8pxタイル基準

        # AUTO / AIR の 8px セルインデックス
        u_auto, v_auto = TILES["AUTO"]
        auto_ul = (u_auto // 8, v_auto // 8)
        auto_ur = ((u_auto + 8) // 8, v_auto // 8)
        auto_ll = (u_auto // 8, (v_auto + 8) // 8)
        auto_lr = ((u_auto + 8) // 8, (v_auto + 8) // 8)

        u_air, v_air = TILES["AIR"]
        air_ul = (u_air // 8, v_air // 8)
        air_ur = ((u_air + 8) // 8, v_air // 8)
        air_ll = (u_air // 8, (v_air + 8) // 8)
        air_lr = ((u_air + 8) // 8, (v_air + 8) // 8)

        visible = (pyxel.frame_count // 90) % 2 == 0
        if getattr(self, "ghost_tiles", None):
            for (tx, ty) in self.ghost_tiles:
                x0 = tx * 2
                y0 = v8_row + ty * 2
                if visible:
                    TM_VAR.pset(x0,     y0,     auto_ul)
                    TM_VAR.pset(x0 + 1, y0,     auto_ur)
                    TM_VAR.pset(x0,     y0 + 1, auto_ll)
                    TM_VAR.pset(x0 + 1, y0 + 1, auto_lr)
                else:
                    TM_VAR.pset(x0,     y0,     air_ul)
                    TM_VAR.pset(x0 + 1, y0,     air_ur)
                    TM_VAR.pset(x0,     y0 + 1, air_ll)
                    TM_VAR.pset(x0 + 1, y0 + 1, air_lr)

        # 全場面でコインと中間フラッグに、プレイヤーと同じ
        # 上下左右1pxの黒い輪郭影を付ける。
        # 先に影を描き、その後TM1本体を重ねるため、色や機能は変わらない。
        if True:
            cam_x = int(getattr(self, "cam_x", 0))
            cam_y = int(getattr(self, "cam_y", 0))
            tx0 = max(0, cam_x // TILE - 1)
            tx1 = min(self.TILES_X - 1, (cam_x + SCREEN_W) // TILE + 1)
            ty0 = max(0, cam_y // TILE - 1)
            ty1 = min(self.TILES_Y - 1, (cam_y + SCREEN_H) // TILE + 1)

            try:
                for col in range(1, 16):
                    pyxel.pal(col, 0)

                for ty in range(ty0, ty1 + 1):
                    for tx in range(tx0, tx1 + 1):
                        tid = tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty)
                        if tid == TILE_COIN:
                            u, v = TILES["COIN"]
                        elif tid == CHECKPOINT:
                            u, v = TILES["MIDFLAG"]
                        else:
                            continue

                        x = tx * TILE
                        y = ty * TILE
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            pyxel.blt(x + dx, y + dy, 0, u, v, TILE, TILE, 0)
            finally:
                pyxel.pal()

        # TM1 を描画
        pyxel.bltm(0, 0, 1, 0, v_row, 144 * TILE, draw_h, 0)

        # Stage9ボス扉のみ、32x32全体へ波が通るようなゆらめき描画を重ねる。
        self.draw_stage9_boss_door_shimmer()

        # 中間フラッグは影の黒色置換が本体へ残って見えないよう、通常色の本体を最後に再描画する。
        # 描画のみの補正で、当たり判定・チェックポイント機能には影響しない。
        try:
            flag_u, flag_v = TILES["MIDFLAG"]
            for ty in range(ty0, ty1 + 1):
                for tx in range(tx0, tx1 + 1):
                    if tile_at(self.level, self.TILES_X, self.TILES_Y, tx, ty) == CHECKPOINT:
                        pyxel.blt(tx * TILE, ty * TILE, 0, flag_u, flag_v, TILE, TILE, 0)
        except Exception:
            pass

        # ========== SPRING 2枚絵（overlay） ==========
        # 注意: TM1 のタイル絵を「上から上書き描画」する方式
        spring_list = getattr(self, "spring_tiles", None)
        if spring_list:
            u1, v1 = TILES["SPRING"]
            u2, v2 = TILES.get("SPRING2", (u1, v1))
            flash = getattr(self, "spring_flash", {})
            # 交互点滅（2枚パターン）
            alt = (pyxel.frame_count // SPRING_ANIM_PERIOD) % 2 == 1

            for (tx, ty) in spring_list:
                # 踏まれた直後は SPRING2 を優先
                pressed = flash.get((tx, ty), 0) > 0
                use2 = not pressed
                u, v = (u2, v2) if use2 else (u1, v1)
                pyxel.blt(tx * TILE, ty * TILE, 0, u, v, TILE, TILE, 0)

    def draw_rain_effect(self):
        """雨環境専用の見た目。小さく疎らな雨粒をワールド最背面寄りに描く。"""
        if getattr(self, "environment", "NONE") != "RAIN":
            return

        # frame_countと画面内の列番号だけで位置を決め、ゲーム状態には一切触れない。
        # 1～2pxの細い粒に限定し、弾やキャラクターより先に描画して視認性を守る。
        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        spacing = 13
        count = SCREEN_W // spacing + 4

        for i in range(count):
            seed = i * 37 + 11
            screen_x = (i * spacing + (seed % 9) - (frame // 5) % spacing) % (SCREEN_W + 12) - 6
            screen_y = (seed * 7 + frame * 2) % (SCREEN_H + 18) - 9
            length = 1 + (seed % 2)
            col = 5 if (seed % 3) else 6
            wx = cam_x + screen_x
            wy = cam_y + screen_y
            pyxel.line(wx, wy, wx, wy + length, col)

    def draw_snow_effect(self):
        """雪環境専用の見た目。雨よりゆっくり横に揺れる、疎らな粉雪を描く。"""
        if getattr(self, "environment", "NONE") != "SNOW":
            return

        # 画面内の位置はframe_countから算出するだけで、ゲーム状態や当たり判定には触れない。
        # 1px中心の粉雪をキャラクター・弾より先に描き、ショットの視認性を維持する。
        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        spacing = 18
        count = SCREEN_W // spacing + 5

        for i in range(count):
            seed = i * 43 + 19
            fall_speed = 1 + (seed % 3 == 0)
            screen_y = (seed * 5 + (frame * fall_speed) // 2) % (SCREEN_H + 20) - 10

            # 左右へゆっくり漂わせ、直線的な雨との違いを出す。
            sway_phase = (frame // 8 + seed) % 24
            sway = sway_phase if sway_phase < 12 else 23 - sway_phase
            sway -= 6
            screen_x = (i * spacing + seed % 11 + sway) % (SCREEN_W + 16) - 8

            wx = cam_x + screen_x
            wy = cam_y + screen_y
            col = 7 if seed % 4 else 6
            pyxel.pset(wx, wy, col)

            # ごく一部だけ2pxの小片にし、密度を増やさず粉雪らしい奥行きを出す。
            if seed % 7 == 0:
                pyxel.pset(wx + 1, wy, col)

    def draw_wind_effect(self):
        """追い風・向かい風の風筋と、時々現れるつむじ風（描画のみ）。"""
        env = getattr(self, "environment", "NONE")
        if env not in ("TAILWIND", "HEADWIND"):
            return

        # 追い風は画面左(X=0方向)から右へ、向かい風はその逆へ流す。
        # frame_countだけから描画位置を算出し、ゲーム状態・当たり判定・移動処理には触れない。
        direction = 1 if env == "TAILWIND" else -1
        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))

        # 本数は従来どおり9本。線を点描状に間引き、暗めの色を中心にして
        # Pyxelの色数の範囲で透明感のある風に見せる。
        for i in range(9):
            seed = i * 47 + 13
            travel = (frame * (2 + seed % 2) + seed * 5) % (SCREEN_W + 48)
            sx = travel - 24 if direction > 0 else SCREEN_W + 24 - travel
            sy = 30 + (seed * 11) % 168
            length = 7 + seed % 8
            bend = ((frame // 6 + seed) % 5) - 2
            col = 5 if seed % 3 else 6

            wx = cam_x + sx
            wy = cam_y + sy

            # 連続線ではなく1pxおきの点描にし、背景を透かして見せる。
            for n in range(length + 1):
                if (n + seed + frame // 4) % 3 == 1:
                    continue
                px = wx + direction * n
                py = wy + (bend * n) // max(1, length * 2)
                pyxel.pset(px, py, col)

            # 先端の巻きも常時は描かず、控えめなアクセントにする。
            if (frame // 5 + seed) % 3 == 0:
                ex = wx + direction * length
                ey = wy + bend // 2
                pyxel.pset(ex - direction, ey + 1, col)

        # つむじ風は常時複数出さず、約4秒周期の短い時間だけ1個を表示する。
        # 位置は周期ごとの疑似乱数で変え、random本体には触れない。
        cycle = frame // 240
        local_frame = frame % 240
        if local_frame < 38:
            seed = cycle * 1103515245 + 12345
            cx_base = 28 + ((seed >> 8) % (SCREEN_W - 56))
            cy = 48 + ((seed >> 16) % 132)

            # 出現中も少し流し、追い風・向かい風の方向感を維持する。
            drift = local_frame * direction
            cx = cx_base + drift
            phase = (frame // 3 + cycle) % 12
            radius = 3 + (phase // 5)
            col = 6
            wx = cam_x + cx
            wy = cam_y + cy

            points = []
            for n in range(8):
                angle = (n + phase) * math.pi / 4.0
                r = max(1.0, radius - n * 0.28)
                px = wx + direction * int(math.cos(angle) * r * 2.0)
                py = wy + int(math.sin(angle) * r)
                points.append((px, py))

            # 渦も線を全部つながず、一部だけ描いて薄く見せる。
            for n in range(len(points) - 1):
                if (n + phase) % 3 == 1:
                    continue
                pyxel.line(points[n][0], points[n][1], points[n + 1][0], points[n + 1][1], col)

    def draw_heat_haze_background(self, v_row, draw_h):
        """酷暑・火事専用：画面下部のTM0背景を蜃気楼のように横へ揺らす。"""
        env = getattr(self, "environment", "NONE")
        if env not in ("HEAT", "FIRE"):
            return

        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        world_h = int(draw_h)

        # 酷暑は下80px、火事は下96px。火事は振幅も少し強くする。
        # TM1より前に行うので、足場・敵・プレイヤーは揺らさない。
        haze_height = 96 if env == "FIRE" else 80
        strength = 1.35 if env == "FIRE" else 1.0
        top = max(0, cam_y + SCREEN_H - haze_height)
        bottom = min(world_h, cam_y + SCREEN_H)
        margin = 8
        src_x = max(0, cam_x - margin)
        width = min(144 * TILE - src_x, SCREEN_W + margin * 2)
        if width <= 0:
            return

        for world_y in range(top, bottom, 2):
            depth = (world_y - top) / max(1.0, bottom - top)
            # 下へ行くほど揺れ幅を増やす。複数周期を重ねて単純な波に見せない。
            wave = (
                math.sin(frame * 0.16 + world_y * 0.23) * (1.5 + depth * 2.0)
                + math.sin(frame * 0.07 - world_y * 0.11) * (0.8 + depth * 1.2)
            )
            shift = int(round(wave * strength))
            dest_x = src_x + shift
            src_y = int(v_row + world_y)
            pyxel.bltm(dest_x, world_y, 0, src_x, src_y, width, 2, 0)

    def draw_gravity_anomaly_effect(self):
        """重力異常専用：白背景でも見える青系粒子がゆっくり上昇する描画のみの演出。"""
        if getattr(self, "environment", "NONE") != "GRAVITY_ANOMALY":
            return

        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))

        # 白背景に埋もれないよう、暗い青の縁＋明るい芯で描く。
        # 密度は増やしすぎず、雪とは違うゆっくりした上昇を維持する。
        for i in range(17):
            seed = i * 67 + 23
            speed_div = 3 + (seed % 3)
            rise = (frame // speed_div + seed * 5) % (SCREEN_H + 28)
            sy = SCREEN_H + 12 - rise

            sway = int(math.sin(frame * 0.025 + seed * 0.31) * (2 + seed % 3))
            sx = (seed * 17 + sway) % (SCREEN_W + 20) - 10

            wx = cam_x + sx
            wy = cam_y + sy

            # 通常粒子：濃いシアン／青の土台に白い芯。
            pyxel.pset(wx, wy, 12)
            if seed % 3 == 0:
                pyxel.pset(wx, wy - 1, 6)
            if seed % 4 == 0:
                pyxel.pset(wx + 1, wy, 7)

            # ごく一部だけ、小さな泡・ひし形にしてアクセントを付ける。
            if seed % 7 == 0:
                pyxel.pset(wx - 1, wy, 6)
                pyxel.pset(wx + 1, wy, 6)
                pyxel.pset(wx, wy - 1, 6)
                pyxel.pset(wx, wy + 1, 6)
                pyxel.pset(wx, wy, 7)

    def high_gravity_pressure_offset(self):
        """高重力時の描画専用オフセット。背景と粒子だけを一瞬1px下へ沈ませる。"""
        if getattr(self, "environment", "NONE") != "HIGH_GRAVITY":
            return 0

        # Pyxel標準30fpsを基準に、78フレーム（約2.6秒）ごとに短く発生。
        # 4フレームだけ1px沈ませ、常時揺れに見えないようにする。
        phase = int(pyxel.frame_count) % 78
        return 1 if 1 <= phase <= 4 else 0

    def draw_high_gravity_effect(self):
        """高重力専用：下降する粒子と細い黒線で、空間が重く沈む印象を加える。"""
        if getattr(self, "environment", "NONE") != "HIGH_GRAVITY":
            return

        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        pressure_y = self.high_gravity_pressure_offset()
        pressure_active = pressure_y > 0

        # 低重力と同系統の青白い粒子を、逆方向（上から下）へゆっくり落とす。
        for i in range(17):
            seed = i * 67 + 23
            speed_div = 3 + (seed % 3)
            fall = (frame // speed_div + seed * 5) % (SCREEN_H + 28)
            sy = -12 + fall

            sway = int(math.sin(frame * 0.025 + seed * 0.31) * (2 + seed % 3))
            sx = (seed * 17 + sway) % (SCREEN_W + 20) - 10

            wx = cam_x + sx
            wy = cam_y + sy + pressure_y

            pyxel.pset(wx, wy, 12)
            if seed % 3 == 0:
                pyxel.pset(wx, wy + 1, 6)
            if seed % 4 == 0:
                pyxel.pset(wx + 1, wy, 7)

            if seed % 7 == 0:
                pyxel.pset(wx - 1, wy, 6)
                pyxel.pset(wx + 1, wy, 6)
                pyxel.pset(wx, wy - 1, 6)
                pyxel.pset(wx, wy + 1, 6)
                pyxel.pset(wx, wy, 7)

        # 黒線を数本ずつ近接配置し、ひと塊の重圧が下へ沈むように見せる。
        # 下へ行くほど本数・濃さ・長さが少し増えるが、視認性を損なわない範囲に抑える。
        try:
            phase = frame // 7
            group_count = 6 if pressure_active else 5
            for group in range(group_count):
                seed = group * 109 + phase * 29 + 17
                center_x = (seed * 37 + group * 41) % SCREEN_W
                speed = 2 + (group % 3)
                sy = (frame * speed + seed * 5) % (SCREEN_H + 64) - 32
                depth = max(0.0, min(1.0, sy / float(max(1, SCREEN_H - 1))))

                # 上側は2本程度、下側では3～4本が近接して一つの束に見える。
                lines_in_group = 2 + int(depth * 2.0)
                if pressure_active and group % 2 == 0:
                    lines_in_group += 1
                lines_in_group = min(4, lines_in_group)

                for j in range(lines_in_group):
                    # 1～3px間隔で並べ、完全な太線ではなく「線の束」にする。
                    offset_x = (j - (lines_in_group - 1) / 2.0) * (1 + seed % 2)
                    sx = int(center_x + offset_x)
                    length = 5 + (seed + j * 5) % 6 + int(depth * 5)
                    wx = cam_x + sx
                    wy = cam_y + sy + pressure_y + j % 2

                    for seg_y in range(length):
                        screen_y = sy + seg_y
                        seg_depth = max(0.0, min(1.0, screen_y / float(max(1, SCREEN_H - 1))))
                        alpha = 0.14 + 0.29 * seg_depth
                        if pressure_active:
                            alpha = min(0.50, alpha + 0.04)
                        pyxel.dither(alpha)
                        pyxel.pset(wx, wy + seg_y, 0)
        finally:
            pyxel.dither(1.0)

    def draw_fire_particles(self):
        """火事専用：火の粉と黒いすすを画面内に舞わせる（描画のみ）。"""
        if getattr(self, "environment", "NONE") != "FIRE":
            return

        frame = int(pyxel.frame_count)
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))

        # 火の粉：下から上へ、少し左右に揺れながら疎らに上昇。
        for i in range(11):
            seed = i * 61 + 17
            life = (frame * (1 + seed % 2) + seed * 7) % (SCREEN_H + 56)
            sy = SCREEN_H + 20 - life
            sway = int(math.sin(frame * 0.10 + seed) * (2 + seed % 3))
            sx = (seed * 13 + frame // (5 + seed % 3) + sway) % (SCREEN_W + 20) - 10
            col = 10 if seed % 3 else 9
            wx, wy = cam_x + sx, cam_y + sy
            pyxel.pset(wx, wy, col)
            if seed % 4 == 0:
                pyxel.pset(wx, wy + 1, 8)

        # すす：黒〜濃灰の小片をゆっくり漂わせる。密度は控えめ。
        for i in range(7):
            seed = i * 79 + 31
            sy = (seed * 5 + frame // (2 + seed % 2)) % (SCREEN_H + 28) - 14
            drift = int(math.sin(frame * 0.045 + seed * 0.3) * 5)
            sx = (seed * 11 + frame // 7 + drift) % (SCREEN_W + 24) - 12
            col = 0 if seed % 3 else 5
            wx, wy = cam_x + sx, cam_y + sy
            pyxel.pset(wx, wy, col)
            if seed % 5 == 0:
                pyxel.pset(wx + 1, wy, col)

        # 画面端の炎：最下部と最上部に、ところどころ小さな炎を描く。
        # あくまで演出用で、当たり判定やゲーム座標には一切影響しない。
        def draw_flame(screen_x, base_screen_y, upward=True, scale=1, phase=0):
            flicker = (frame // 3 + phase) % 3
            wx = cam_x + int(screen_x)
            wy = cam_y + int(base_screen_y)

            # 外側の赤、中央のオレンジ、芯の黄で小さな炎を構成。
            if upward:
                h = 7 + scale * 2 + (1 if flicker == 1 else 0)
                pyxel.line(wx, wy, wx, wy - h, 8)
                pyxel.line(wx - 2, wy, wx - 1, wy - max(3, h - 3), 8)
                pyxel.line(wx + 2, wy, wx + 1, wy - max(4, h - 2), 8)
                pyxel.line(wx, wy - 1, wx, wy - max(3, h - 3), 9)
                pyxel.pset(wx, wy - max(2, h - 5), 10)
                if flicker == 2:
                    pyxel.pset(wx + 1, wy - h - 1, 9)
            else:
                h = 6 + scale * 2 + (1 if flicker == 0 else 0)
                pyxel.line(wx, wy, wx, wy + h, 8)
                pyxel.line(wx - 2, wy, wx - 1, wy + max(3, h - 3), 8)
                pyxel.line(wx + 2, wy, wx + 1, wy + max(4, h - 2), 8)
                pyxel.line(wx, wy + 1, wx, wy + max(3, h - 3), 9)
                pyxel.pset(wx, wy + max(2, h - 5), 10)
                if flicker == 1:
                    pyxel.pset(wx - 1, wy + h + 1, 9)

        # 下端：数か所だけ。フレームごとに少し伸縮して炎らしく見せる。
        bottom_flames = ((18, 1, 0), (73, 0, 2), (151, 1, 1), (226, 0, 4))
        for sx, scale, phase in bottom_flames:
            draw_flame(sx, SCREEN_H - 1, upward=True, scale=scale, phase=phase)

        # 上端：垂れ込む炎を少数だけ配置し、画面を覆いすぎないようにする。
        top_flames = ((42, 0, 3), (119, 1, 0), (207, 0, 2))
        for sx, scale, phase in top_flames:
            draw_flame(sx, 0, upward=False, scale=scale, phase=phase)

    def earthquake_draw_offset(self):
        """地震の予兆・本震に使う描画専用オフセット。ゲーム座標は変更しない。"""
        if getattr(self, "environment", "NONE") != "EARTHQUAKE":
            return 0, 0

        # 予兆中は、一瞬の左右揺れを2回だけ出す。
        if getattr(self, "earthquake_pending", False):
            t = int(getattr(self, "earthquake_warning_timer", 0))
            burst = (94 >= t >= 89) or (52 >= t >= 45)
            if burst:
                phase = (EARTHQUAKE_WARNING_FRAMES - t)
                return (2 if phase % 2 == 0 else -2), 0
            return 0, 0

        # 本震は素早く細かいXY揺れ。描画カメラだけを動かす。
        vt = int(getattr(self, "earthquake_visual_timer", 0))
        if vt > 0:
            pattern_x = (-3, 3, -2, 2, -4, 4, -1, 1)
            pattern_y = (1, -1, 2, -2, 0, 1, -1, 0)
            idx = (28 - vt) % len(pattern_x)
            return pattern_x[idx], pattern_y[idx]
        return 0, 0

    def draw_earthquake_flash(self):
        """本震中だけ、画面全体を細かく点滅させる（描画のみ）。"""
        if getattr(self, "environment", "NONE") != "EARTHQUAKE":
            return
        vt = int(getattr(self, "earthquake_visual_timer", 0))
        if vt <= 0:
            return
        # 1フレームおきに薄い白、数フレームおきに薄い黒を重ねる。
        try:
            if vt % 2 == 0:
                pyxel.dither(0.22)
                pyxel.rect(0, 0, SCREEN_W, SCREEN_H, 7)
            elif vt % 5 == 0:
                pyxel.dither(0.16)
                pyxel.rect(0, 0, SCREEN_W, SCREEN_H, 0)
        finally:
            pyxel.dither(1.0)

    def draw_fog_overlay(self):
        """霧専用：Stage5暗闇処理の白版。楕円内は見え、外側ほど白く霞む。"""
        if getattr(self, "environment", "NONE") != "FOG":
            return
        if not getattr(self, "player", None):
            return

        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        px = int(self.player.x + self.player.w // 2 - cam_x)
        py = int(self.player.y + self.player.h // 2 - cam_y)

        # Stage5暗闇より広い可視範囲。四角い枠は作らず楕円境界だけをぼかす。
        rx = 154
        ry = 82
        feather = 42
        outer_rx = rx + feather
        outer_ry = ry + feather

        def half_width(radius_x, radius_y, dy):
            if radius_y <= 0 or abs(dy) > radius_y:
                return None
            v = 1.0 - (dy * dy) / float(radius_y * radius_y)
            if v <= 0:
                return 0
            return int(radius_x * math.sqrt(v))

        try:
            for y in range(SCREEN_H):
                dy = y - py
                outer_hw = half_width(outer_rx, outer_ry, dy)

                # 外側は白い濃霧。ただしditherで背景を少し残す。
                if outer_hw is None:
                    pyxel.dither(0.72)
                    pyxel.rect(0, y, SCREEN_W, 1, 7)
                    continue

                ox1 = max(0, px - outer_hw)
                ox2 = min(SCREEN_W, px + outer_hw)
                pyxel.dither(0.72)
                if ox1 > 0:
                    pyxel.rect(0, y, ox1, 1, 7)
                if ox2 < SCREEN_W:
                    pyxel.rect(ox2, y, SCREEN_W - ox2, 1, 7)

                inner_hw = half_width(rx, ry, dy)
                if inner_hw is None:
                    inner_hw = 0
                ix1 = max(0, px - inner_hw)
                ix2 = min(SCREEN_W, px + inner_hw)

                # 楕円境界を複数の細い帯で段階的に白くする。
                for x_start, x_end, reverse in ((ox1, ix1, False), (ix2, ox2, True)):
                    width = x_end - x_start
                    if width <= 0:
                        continue
                    steps = max(1, width // 4)
                    for i in range(steps):
                        a = i / max(1, steps - 1)
                        if reverse:
                            a = 1.0 - a
                        alpha = 0.64 * (1.0 - a)
                        xa = x_start + (width * i) // steps
                        xb = x_start + (width * (i + 1)) // steps
                        if xb > xa:
                            pyxel.dither(alpha)
                            pyxel.rect(xa, y, xb - xa, 1, 7)
        finally:
            pyxel.dither(1.0)

    def draw_cave_darkness_overlay(self):
        """Stage5/8専用: プレイヤー周辺だけ見える洞窟風の暗幕。

        Stage9は全ステージのタイルマップを縦につなげた構成なので、
        Stage9内でStage5/8相当のマップ部分を読み込んでいても暗幕は出さない。
        """
        current_stage = int(getattr(self, "stage", 1) or 1)
        if current_stage == 9:
            return
        if current_stage not in (5, 8):
            return
        # 火事中も暗闇は残すが、炎の明かりで通常時より広く・明るく見えるようにする。
        fire_light = getattr(self, "environment", "NONE") == "FIRE"

        # プレイヤー中心を画面座標へ変換（UIは暗くしないため camera() 解除後に呼ぶ）
        cam_x = int(getattr(self, "cam_x", 0))
        cam_y = int(getattr(self, "cam_y", 0))
        px = int(self.player.x + self.player.w // 2 - cam_x)
        py = int(self.player.y + self.player.h // 2 - cam_y)

        # 見える範囲：横スクロール向けに横長の楕円。
        # rx=128 なので、プレイヤーが画面端付近にいると画面中央あたりまで見える。
        if fire_light:
            rx = 154      # 火事中は炎の明かりで通常より広く見える
            ry = 76
            feather = 38
        else:
            rx = 128
            ry = 56       # 高さは前回の見え方に近い
            feather = 30  # 境界のぼかし幅
        outer_rx = rx + feather
        outer_ry = ry + feather

        def _span_half_width(radius_x, radius_y, dy):
            """楕円の指定Yにおける半幅を返す。範囲外ならNone。"""
            if radius_y <= 0 or abs(dy) > radius_y:
                return None
            v = 1.0 - (dy * dy) / float(radius_y * radius_y)
            if v <= 0:
                return 0
            return int(radius_x * (v ** 0.5))

        # 外側は完全に黒。内側は描かない。境界だけditherで段階的に暗くする。
        old_dither = 1.0
        try:
            for y in range(SCREEN_H):
                dy = y - py
                outer_hw = _span_half_width(outer_rx, outer_ry, dy)

                # 外側楕円のさらに外は、火事中でも完全な暗闇にする。
                # プレイヤーからかなり遠い場所は見えず、近～中距離だけ炎で通常時より見やすい。
                if outer_hw is None:
                    pyxel.dither(1.0)
                    pyxel.rect(0, y, SCREEN_W, 1, 0)
                    continue

                ox1 = max(0, px - outer_hw)
                ox2 = min(SCREEN_W, px + outer_hw)
                # 外縁より遠い左右は完全な黒。炎の明るさはぼかし帯の内側だけに限定する。
                pyxel.dither(1.0)
                if ox1 > 0:
                    pyxel.rect(0, y, ox1, 1, 0)
                if ox2 < SCREEN_W:
                    pyxel.rect(ox2, y, SCREEN_W - ox2, 1, 0)

                inner_hw = _span_half_width(rx, ry, dy)
                if inner_hw is None:
                    inner_hw = 0

                ix1 = max(0, px - inner_hw)
                ix2 = min(SCREEN_W, px + inner_hw)

                # 楕円境界のぼかし。外側ほど黒を濃く、内側ほど薄くする。
                left_w = max(0, ix1 - ox1)
                right_w = max(0, ox2 - ix2)

                if left_w > 0:
                    left_alphas = ((0, 0.58), (1, 0.44), (2, 0.30), (3, 0.16)) if fire_light else ((0, 0.85), (1, 0.65), (2, 0.45), (3, 0.25))
                    for step, alpha in left_alphas:
                        x_start = ox1 + (left_w * step) // 4
                        x_end = ox1 + (left_w * (step + 1)) // 4
                        if x_end > x_start:
                            pyxel.dither(alpha)
                            pyxel.rect(x_start, y, x_end - x_start, 1, 0)

                if right_w > 0:
                    right_alphas = ((0, 0.16), (1, 0.30), (2, 0.44), (3, 0.58)) if fire_light else ((0, 0.25), (1, 0.45), (2, 0.65), (3, 0.85))
                    for step, alpha in right_alphas:
                        x_start = ix2 + (right_w * step) // 4
                        x_end = ix2 + (right_w * (step + 1)) // 4
                        if x_end > x_start:
                            pyxel.dither(alpha)
                            pyxel.rect(x_start, y, x_end - x_start, 1, 0)
        finally:
            # 他の描画にditherが残らないよう戻す
            try:
                pyxel.dither(old_dither)
            except Exception:
                pass

    def draw(self):
    # ← 一番最初に入れる（他の描画より前）
        self.bg_col = self.stage_bg_color_map.get(self.stage or 1, 12)
        bg = self.bg_col
        try:
            if getattr(self, "environment", "NONE") in ("GRAVITY_ANOMALY", "HIGH_GRAVITY"):
                # 低重力／高重力で共通の青白い空間背景
                bg = 7
        except Exception:
            pass
        pyxel.cls(bg)
    # （以降の背景描画で色を固定している箇所があれば、下のBで直す）
        if self.scene == "TITLE":
            if not self.dev_mode:
                # Normal title: START / CONTINUE / CONFIG.
                menu_index = int(getattr(self, "title_menu_index", 0))
                self.draw_shadow_text(72, 98, ("> " if menu_index == 0 else "  ") + "START", 11 if menu_index == 0 else 7)
                continue_available = (
                    self.last_failed_stage is not None and
                    self.score >= Game.CONTINUE_COST
                )
                cont_color = 11 if (menu_index == 1 and continue_available) else (8 if not continue_available else 7)
                self.draw_shadow_text(72, 110, ("> " if menu_index == 1 else "  ") + "CONTINUE", cont_color)
                self.draw_shadow_text(72, 122, ("> " if menu_index == 2 else "  ") + "CONFIG", 11 if menu_index == 2 else 7)
            else:
                self.draw_shadow_text(78, 76, "MY PLATFORMER", 10)
                self.draw_shadow_text(46, 92, "UP/DOWN: SELECT  LEFT/RIGHT: CHANGE", 7)
                self.draw_shadow_text(72, 102, "RETURN: DECIDE / START", 7)

            # --- デバッグ時だけ表示：全項目カーソル選択式 ---
            if self.dev_mode:
                menu_index = int(getattr(self, "dev_menu_index", 0))
                dev_t = DEV_START_TIME_OPTIONS[int(getattr(self, "dev_start_time_index", 0))]
                dev_t_label = "NO LIMIT" if dev_t == DEV_TIME_NO_LIMIT else str(dev_t) + "s"
                dev_env = ENV_TYPES[int(getattr(self, "dev_environment_index", 0))]
                rows = [
                    f"DEV STAGE  <{self.dev_stage_select}>",
                    f"DEV BOSS   <{self.dev_boss_stage_select}>",
                    f"DEV MID    <{self.dev_boss_stage_select}>",
                    f"DEV FINAL  <P{self.dev_final_phase_select}>",
                    f"DEV TIME   <{dev_t_label}>",
                    f"DEV ENV    <{ENV_LABELS.get(dev_env, dev_env)}>",
                ]
                for idx, label in enumerate(rows):
                    prefix = "> " if idx == menu_index else "  "
                    color = 11 if idx == menu_index else 13
                    self.draw_shadow_text(42, 126 + idx * 12, prefix + label, color)

        elif self.scene == "CONFIG":
            self.draw_shadow_text(68, 54, "CONTROLLER CONFIG", 10)
            self.draw_shadow_text(36, 68, "D-PAD: FIXED", 7)
            menu_index = int(getattr(self, "config_menu_index", 0))
            capture_action = getattr(self, "config_capture_action", None)
            rows = [
                ("JUMP", "JUMP"),
                ("SHOT", "SHOT"),
                ("DASH", "DASH (HOLD)"),
                ("START_PAUSE", "START / PAUSE"),
            ]
            for idx, (action, label) in enumerate(rows):
                prefix = "> " if idx == menu_index and capture_action is None else "  "
                key_name = _keyboard_key_short_name(KEYBOARD_BINDINGS[action])
                button_name = _gamepad_button_short_name(GAMEPAD_BINDINGS[action])
                color = 11 if idx == menu_index and capture_action is None else 7
                self.draw_shadow_text(24, 92 + idx * 16, prefix + label, color)
                self.draw_shadow_text(122, 92 + idx * 16, "K:" + key_name, 13 if capture_action != action else 10)
                self.draw_shadow_text(174, 92 + idx * 16, "G:" + button_name, 13 if capture_action != action else 10)

            reset_prefix = "> " if menu_index == 4 and capture_action is None else "  "
            back_prefix = "> " if menu_index == 5 and capture_action is None else "  "
            self.draw_shadow_text(34, 164, reset_prefix + "RESET DEFAULT", 11 if menu_index == 4 and capture_action is None else 7)
            self.draw_shadow_text(34, 180, back_prefix + "BACK", 11 if menu_index == 5 and capture_action is None else 7)

            if capture_action is not None:
                self.draw_shadow_text(20, 208, "PRESS KEY / BUTTON: " + capture_action.replace("_", "/"), 10)
                self.draw_shadow_text(62, 220, "ESC: CANCEL", 7)
            else:
                self.draw_shadow_text(26, 208, "RETURN/A: SELECT   UP/DOWN: MOVE", 7)
                self.draw_shadow_text(28, 220, "K:KEYBOARD  G:GAMEPAD/V-PAD", 7)

        elif self.scene == "PLAY":
            quake_dx, quake_dy = self.earthquake_draw_offset()
            pyxel.camera(self.cam_x - quake_dx, getattr(self, "cam_y", 0) - quake_dy)
            self.draw_level()
            self.draw_rain_effect()
            self.draw_snow_effect()
            self.draw_wind_effect()
            self.draw_gravity_anomaly_effect()
            self.draw_high_gravity_effect()
            self.draw_fire_particles()
            for p in self.platforms: p.draw()
            for e in self.enemies:
                if stage9_normal_enemy_section_active(self, e):
                    e.draw()
            if (self.midboss and self.midboss.alive
                    and normal_stage4_midboss_active(self)):
                self.midboss.draw()
                self._draw_stage9_midboss_lock_mist()
            for fb in getattr(self, "field_midbosses", []):
                if fb.alive and stage9_field_actor_active(self, fb):
                    fb.draw()
            for fb in getattr(self, "field_bosses", []):
                if fb.alive:
                    # Stage9歴代Stage7ボス限定：既存のワープ準備タイマーを
                    # フィールド描画にも反映し、ワープ前に予告点滅させる。
                    is_stage9_stage7_boss = (
                        int(getattr(self, "stage", 0)) == 9
                        and int(getattr(fb, "field_boss_origin_stage", 0)) == 7
                        and not bool(getattr(fb, "is_midboss", False))
                    )
                    blink = int(getattr(fb, "_final_phase_blink_timer", 0) or 0) if is_stage9_stage7_boss else 0
                    if blink <= 0 or (pyxel.frame_count // 3) % 2 == 0:
                        fb.draw()
            if int(getattr(self, "stage", 0)) == 9:
                self.draw_stage5_boss_hit_effects()
            self.draw_midboss_explosion_effect()
            self.draw_defeated_boss_effect(was_stage_boss=False)
            self.reaper.draw()
            for it in self.items: it.draw()
            for gem in getattr(self, "stage9_gems", []):
                if gem.alive:
                    gem.draw()
            for b in self.bullets: b.draw()
            for eb in self.enemy_bullets: eb.draw()
            self.draw_player_with_effect()
            pyxel.camera()
            self.draw_earthquake_flash()
            self.draw_fog_overlay()
            self.draw_cave_darkness_overlay()
            self.draw_screen_notice()

            self.draw_shadow_text(4, 4,  f"STAGE {self.stage}", 7)
            self.draw_shadow_text(80, 4, f"LIVES:{self.lives}", 7)
            time_text = "INF" if getattr(self, "time_limit_disabled", False) else str(self.time_limit // 60)
            self.draw_shadow_text(200, 4, f"TIME:{time_text}", 7)
            self.draw_shadow_text(4, 16, f"SCORE:{self.score}", 7)
            if int(getattr(self, "stage", 0)) == 9:
                # Simple numeric gem HUD as requested. Small crystal mark + number only.
                pyxel.line(167, 4, 171, 8, 12)
                pyxel.line(171, 8, 167, 12, 6)
                pyxel.line(167, 12, 163, 8, 12)
                pyxel.line(163, 8, 167, 4, 7)
                self.draw_shadow_text(175, 5, str(int(getattr(self, "stage9_gem_count", 0))), 7)
                if getattr(self, "stage9_hint_timer", 0) > 0:
                    self.draw_shadow_text(78, 36, "COLLECT THE GEMS", 10)
            if self.cp_active:
                self.draw_shadow_text(200, 16, "CP", 11)

        elif self.scene == "BOSS":
            quake_dx, quake_dy = self.earthquake_draw_offset()
            pyxel.camera(self.cam_x - quake_dx, -quake_dy)
            self.draw_level()
            self.draw_stage9_final_boss_backdrop()
            # 通常ステージ9と同じ、警報のような赤い点滅をラスボス部屋にも反映する。
            self.draw_stage9_alarm_lights_background()
            self.draw_rain_effect()
            self.draw_snow_effect()
            self.draw_wind_effect()
            self.draw_gravity_anomaly_effect()
            self.draw_high_gravity_effect()
            self.draw_fire_particles()
            for p in self.platforms: p.draw()
            # TM1と移動床等を描いた後に床を補修し、ラスボス部屋の見た目の穴を消す。
            self.draw_stage9_final_boss_floor_overlay()
            for e in self.enemies:
                if stage9_normal_enemy_section_active(self, e):
                    e.draw()
            if self.boss and self.boss.alive:
                blink = int(getattr(self.boss, "_final_phase_blink_timer", 0) or 0)
                if blink <= 0 or (pyxel.frame_count // 3) % 2 == 0:
                    self.boss.draw()
            self.draw_stage5_boss_hit_effects()
            self.draw_defeated_boss_effect(was_stage_boss=True)
            for b in self.bullets: b.draw()
            for eb in self.enemy_bullets: eb.draw()
            self.draw_player_with_effect()
            pyxel.camera()
            self.draw_earthquake_flash()
            self.draw_fog_overlay()
            self.draw_cave_darkness_overlay()
            self.draw_screen_notice()

            self.draw_shadow_text(4, 4,  f"STAGE {self.stage}", 7)
            self.draw_shadow_text(80, 4, f"LIVES:{self.lives}", 7)
            time_text = "INF" if getattr(self, "time_limit_disabled", False) else str(self.time_limit // 60)
            self.draw_shadow_text(200, 4, f"TIME:{time_text}", 7)
            self.draw_shadow_text(4, 16, f"SCORE:{self.score}", 7)

            if self.boss:
                max_hp = max(1, int(getattr(self.boss, "max_hp", getattr(self.boss, "hp", 30))))
                cur = max(0, min(int(getattr(self.boss, "hp", 0)), max_hp))
                # HP60のラスボスでも見やすいよう、最大HPに応じてバー幅を少し広げる。
                bar_w = 150 if max_hp >= 60 else 120
                x0, y0 = (52, 24) if bar_w >= 150 else (68, 24)
                hp_col = 11 if self.stage == 9 else 8  # Stage9は赤系背景対策で青系
                pyxel.rectb(x0-1, y0-1, bar_w+2, 6, 7)
                fill_w = int(bar_w * (cur / max_hp))
                if fill_w > 0:
                    pyxel.rect(x0, y0, fill_w, 4, hp_col)
                self.draw_shadow_text(x0 + bar_w + 6, y0 - 1, f"HP {cur}/{max_hp}", 7)

        elif self.scene == "CLEAR":
            if self.stage == 9:
                # Stage9 boss defeat ending message + final score display
                self.draw_shadow_text(84, 84, "CONGRATULATIONS!", 10)
                self.draw_shadow_text(56, 100, "YOU COMPLETED THE MISSION", 7)
                self.draw_shadow_text(74, 112, "PERFECTLY!", 7)
                self.draw_shadow_text(74, 124, "TRY AGAIN ANYTIME!", 7)
                self.draw_shadow_text(72, 136, f"{self.clear_bonus_rank} +{self.clear_bonus_base}", 10)
                self.draw_shadow_text(62, 148, f"TIME BONUS +{self.clear_bonus_time}", 7)
                self.draw_shadow_text(62, 160, f"LIFE BONUS +{self.final_life_bonus}", 11)
                self.draw_shadow_text(82, 174, f"SCORE: {self.score}", 10)
                self.draw_shadow_text(60, 190, "PRESS RETURN TO TITLE", 7)
            else:
                msg = "HIDDEN STAGE UNLOCKED!" if (self.stage==5 and self.score>=5000) else f"STAGE {self.stage} CLEAR!"
                self.draw_shadow_text(60, 88, msg, 10)
                self.draw_shadow_text(76, 104, f"{self.clear_bonus_rank} +{self.clear_bonus_base}", 10)
                self.draw_shadow_text(66, 118, f"TIME BONUS +{self.clear_bonus_time}", 7)
                self.draw_shadow_text(70, 130, f"CLEAR TOTAL +{self.clear_bonus_total}", 7)
                self.draw_shadow_text(82, 142, f"SCORE: {self.score}", 10)
                self.draw_shadow_text(60, 158, "PRESS RETURN TO CONTINUE", 7)

                # ステージ8クリア時、条件未達なら必要点数だけを匂わせ表示
                if self.stage == 8 and (not self.stage9_reached) and self.score < Game.STAGE9_UNLOCK_SCORE:
                    self.draw_shadow_text(64, 174, "NEED 100,000+ POINTS", 8)

        elif self.scene == "GAMEOVER":
            # ゲームオーバー時は案内文を出さず、GAME OVER のみ表示する。
            self.draw_shadow_text(100, 100, "GAME OVER", 8)

        if self.paused and self.scene in ("PLAY", "BOSS"):
            # 説明が2行になったため、帯を内容に合う高さへ縮小。
            # Pyxelのディザ描画で背景が透ける濃紺の半透明風表示にする。
            pyxel.dither(0.65)
            pyxel.rect(0, 88, SCREEN_W, 40, 1)
            pyxel.dither(1.0)
            self.draw_shadow_text(SCREEN_W//2 - 18, 92,  "PAUSED", 10)
            self.draw_shadow_text(SCREEN_W//2 - 64, 108, "PRESS P TO RESUME", 7)
# === ANCHOR END ===

# ===== 実行 =====
# === ANCHOR: EXECUTION (DO NOT EDIT) ===
Game()
# === ANCHOR END ===
