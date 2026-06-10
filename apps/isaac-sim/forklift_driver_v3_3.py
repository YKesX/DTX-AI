# forklift_driver_v3_3.py
# Isaac Sim 4.5 — DTX-AI Forklift Oto-Sürücü v3.3
#
# DEĞIŞIKLIK v3.2'ye göre:
#   [UPD] FAULT_SEQUENCE 3 tura çıktı (0-450s). Loop ~76s → 450s / 76s ≈ 5.9
#         tekrar yapar, forklift tüm kayıt boyunca hareket eder.
#         Başka değişiklik yok; ileri-geri mantığı korundu.
#
# KULLANIM:
#   1. dtx_story_v2.8.py → Ctrl+Enter
#   2. Bu dosya → Ctrl+Enter (ayrı tab)
#   3. PLAY

import omni.kit.app
import omni.timeline
import carb
import numpy as np

from omni.isaac.core import World
from omni.isaac.core.utils.types import ArticulationAction
from isaacsim.core.prims import SingleArticulation

FORKLIFT_ROOT = "/World/forklift_b_sensor"

DOF_LIFT  = "lift_joint"
DOF_DRIVE = "back_wheel_drive"
DOF_STEER = "back_wheel_swivel"

DRIVE_FWD  =  0.50
DRIVE_BCK  = -0.50
DRIVE_STOP =  0.0
STEER_STR  =  0.0
STEER_R    =  0.35
STEER_L    = -0.35
LIFT_UP    = -0.12
LIFT_DOWN  = -0.045

# -----------------------------------------------------------------------
# Carry loop: (süre_s, drive, steer, lift)
# Toplam: ~76s — yaklaşık eşit ileri/geri mesafe
# İleri toplam: 5+10+8 = 23s × 0.50 = 11.5m
# Geri toplam:  2.5+8+10 = 20.5s × 0.50 = 10.25m
# → Forklift aynı bölgede ileri-geri hareket eder, duvara dayanmaz
# -----------------------------------------------------------------------
CARRY_LOOP = [
    # --- İLERİ FAZ ---
    (5.0,  DRIVE_FWD,  STEER_STR, LIFT_DOWN),  # ileri git
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # dur
    (3.0,  DRIVE_STOP, STEER_STR, LIFT_UP),    # kaldır
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_UP),    # bekle
    (10.0, DRIVE_FWD,  STEER_STR, LIFT_UP),    # taşı
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_UP),    # dur
    (3.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # indir
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # bekle
    # Hafif dönüş
    (3.0,  DRIVE_FWD,  STEER_R,   LIFT_DOWN),  # sağa dön
    (3.0,  DRIVE_FWD,  STEER_L,   LIFT_DOWN),  # düzelt
    (8.0,  DRIVE_FWD,  STEER_STR, LIFT_DOWN),  # devam ileri

    # --- GERİ FAZI (duvara dayanmadan geri dön) ---
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # dur
    (2.5,  DRIVE_BCK,  STEER_STR, LIFT_DOWN),  # geri çekil
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # dur
    (3.0,  DRIVE_STOP, STEER_STR, LIFT_UP),    # kaldır
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_UP),    # bekle
    (8.0,  DRIVE_BCK,  STEER_STR, LIFT_UP),    # geri taşı
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_UP),    # dur
    (3.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # indir
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # bekle
    # Hafif dönüş geri yönde
    (3.0,  DRIVE_BCK,  STEER_R,   LIFT_DOWN),  # sağa dön
    (3.0,  DRIVE_BCK,  STEER_L,   LIFT_DOWN),  # düzelt
    (10.0, DRIVE_BCK,  STEER_STR, LIFT_DOWN),  # devam geri
    (1.0,  DRIVE_STOP, STEER_STR, LIFT_DOWN),  # dur — loop başa döner
]

# -----------------------------------------------------------------------

class ForkliftDriver:
    def __init__(self):
        self._art         = None
        self._ctrl        = None
        self._was_playing = False
        self._loop_step   = 0
        self._step_timer  = 0.0
        self._idx_drive   = None
        self._idx_lift    = None
        self._idx_steer   = None
        self._n_dofs      = 0

        self._app_sub = omni.kit.app.get_app().get_update_event_stream() \
            .create_subscription_to_pop(self._on_update, name="dtx_driver_v3_3")
        carb.log_warn("[DRIVER v3.3] Ready. Press PLAY.")

    def _on_update(self, event):
        tl = omni.timeline.get_timeline_interface()
        playing = tl.is_playing()
        if playing and not self._was_playing:
            self._was_playing = True
            self._init()
        elif not playing and self._was_playing:
            self._was_playing = False
            self._stop()
        if playing and self._art is not None:
            dt = event.payload.get("dt", 1.0 / 60.0)
            self._tick(dt)

    def _init(self):
        try:
            self._art = SingleArticulation(prim_path=FORKLIFT_ROOT, name="dtx_driver_v3_3_art")
            self._art.initialize()
            names = list(self._art.dof_names)
            carb.log_warn("[DRIVER v3.3] DOFs: " + str(names))
            self._n_dofs = len(names)

            def find(kw):
                for i, n in enumerate(names):
                    if kw in n: return i
                return None

            self._idx_drive = find(DOF_DRIVE)
            self._idx_lift  = find(DOF_LIFT)
            self._idx_steer = find(DOF_STEER)
            carb.log_warn(f"[DRIVER v3.3] idx — drive:{self._idx_drive} lift:{self._idx_lift} steer:{self._idx_steer}")

            self._ctrl = self._art.get_articulation_controller()
            self._loop_step  = 0
            self._step_timer = 0.0
            carb.log_warn("[DRIVER v3.3] Auto-drive başlıyor (ileri-geri loop).")
        except Exception as exc:
            carb.log_warn("[DRIVER v3.3] Init hatası: " + str(exc))
            self._art = self._ctrl = None

    def _tick(self, dt: float):
        if self._ctrl is None:
            return
        try:
            dur, drv, steer, lift = CARRY_LOOP[self._loop_step]
        except IndexError:
            self._loop_step = 0
            return

        vels = [None] * self._n_dofs
        pos  = [None] * self._n_dofs

        if self._idx_drive is not None:
            vels[self._idx_drive] = drv
        if self._idx_steer is not None:
            pos[self._idx_steer] = steer
        if self._idx_lift is not None:
            pos[self._idx_lift] = lift

        self._ctrl.apply_action(ArticulationAction(
            joint_velocities=vels,
            joint_positions=pos,
        ))

        self._step_timer += dt
        if self._step_timer >= dur:
            self._step_timer = 0.0
            self._loop_step  = (self._loop_step + 1) % len(CARRY_LOOP)

    def _stop(self):
        if self._ctrl is not None:
            try:
                vels = [None] * self._n_dofs
                if self._idx_drive is not None:
                    vels[self._idx_drive] = 0.0
                self._ctrl.apply_action(ArticulationAction(joint_velocities=vels))
            except Exception:
                pass
        carb.log_warn("[DRIVER v3.3] Durduruldu.")

    def destroy(self):
        self._stop()
        self._app_sub = None


try:
    _driver.destroy()
    carb.log_warn("[DRIVER v3.3] Eski driver temizlendi.")
except (NameError, AttributeError):
    pass

_driver = ForkliftDriver()
