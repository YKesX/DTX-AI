# -*- coding: utf-8 -*-
# =============================================================================
# DTX-AI Forklift Sensor Logger
# Version : 2.17.0
# Isaac Sim: 4.5
# GitHub : https://github.com/YKesX/DTX-AI
#
# Changes vs 2.16.0 (v2.17.0):
# [FIX1] nominal'de aktif soğuma: sıcaklık > amb+2°C iken THERMAL_BETA×5
#        → overheat sonrası nominal label kirlenmiyor (max 78°C → ~33°C)
# [FIX2] FAULT_SEQUENCE yeniden dengelendi: bearing_wear ve pressure_fault
#        35s pencere (önceki 25s → 3072/3000 satır eksikliği giderildi)
# [FIX3] pressure_fault injection: lift_force_z ×0.25 (önceki ×0.45) ve
#        flutter 1800W (önceki 800W) — gürültü sinyali bastırmasın
#
# Changes vs 2.15.0 (v2.16.0):
# [FIX1] Fault signal injection eklendi: bearing_wear (titreşim+effort), overload
#        (lift_force_z+pressure), pressure_fault (basınç düşüşü+flutter),
#        wheel_slip (roller overspeed+effort düşüşü). Isaac Sim'de fizik
#        parametresi manipülasyonu sensör okumasını yeterince etkilemediği
#        yerlerde doğrudan sinyal pertürbasyon kullanılıyor.
#
# Changes vs 2.14.0 (v2.15.0):
# [FIX1] _on_physics_step'teki _active_physics_fault/_ramp_state/_payload_added
#        sıfırlamaları kaldırıldı. Bu 3 satır her adımda fault fiziklerini override
#        ediyordu → tüm classlar aynı sensör değerini üretiyordu.
# [FIX2] scenario_tick → thermal integratör sırası düzeltildi. Artık beta
#        güncellendikten SONRA integratör çalışır. Overheat ~62°C'ye ulaşır.
#
# Changes vs 2.13.0 (v2.14.0):
# [FIX1] self._thermal_beta __init__'te explicit initialize edildi (=THERMAL_BETA).
#        Önceden sadece _scenario_tick'in else dalında set ediliyordu; ilk
#        adımda AttributeError riski + overheat penceresi girerken eski değer kalıyordu.
# [FIX2] _scenario_tick CSV yazımından ÖNCE çağrılıyor. Önceki sırada beta bu
#        adımda güncelleniyor, thermal integratör bir sonraki adımda görüyordu.
#        Şimdi: scenario_tick → beta güncelle → integratör yeni beta ile çalış → CSV yaz.
# [FIX3] Thermal input: vel*effort (dur fazlarında 0) → effort^2/SCALE (her zaman nonzero).
#        DRIVE_STOP adımlarında power=0 → integratör soğuyor → fault bantları kayboluyor.
#        effort^2 motora verilen akım proxyi, forklift dursa da motor enerjilidir.
#        Beklenen bantlar: nominal≈32°C, overheat≈62°C, bearing_wear≈68°C, wheel_slip≈29°C.
# [FIX4] RAMP_IN/OUT 5s→2s: boş label transition süresi %25→<%1'e düşer.
# [FIX5] FAULT_SEQUENCE 4. tur eklendi (450-600s): simülasyon ne kadar sürerse sürsün
#        boş label kalmaz.
# [FIX4] Thermal integrator now scales by actual dt*PHYSICS_RATE_HZ so
#        temperature evolves correctly when Isaac Sim runs slower than
#        the nominal 60 Hz (e.g. on test machines at ~1.8× real-time).
# [FIX5] temperature_c and power_dissipated_w excluded from spike
#        injection (SPIKE_EXEMPT set). These are derived integrator
#        values, not raw sensor readings; 5-10σ spikes on them are
#        physically nonsensical and corrupt ML training labels.
# [FIX6] temperature_c decoupled from drive/lift dropout cascade.
#        A real thermal sensor does not go null when a joint encoder
#        drops. temperature_c now has its own independent low-probability
#        dropout (TEMP_DROPOUT_PROB = 0.001, i.e. 0.1% per tick).
# [FIX7] CSV flushed every FLUSH_INTERVAL_STEPS steps (~5 s at 60 Hz)
#        to prevent data loss on crash or forced stop.
#
# Changes vs 2.2.0 (v2.2.1):
# [FIX1] POWER_SPIKE_MAX clamp (5000 W): raw eff_power still recorded in
#        CSV but thermal integrator only sees min(eff_power, 5000 W).
#        Prevents non-physical impulse spikes (teleport, external force)
#        from permanently corrupting temperature_c.
# [FIX2] THERMAL_MAX_C hard ceiling (150 C): secondary safeguard against
#        accumulator runaway from any sustained non-physical energy input.
# [FIX3] power_dissipated_w clamped to >= 0.0 at write-time in fmt().
#        Gaussian noise on near-zero clean values could produce negative
#        power. Raw noised value still used for rolling stats; only the
#        CSV output is clamped.
#
# Changes vs 2.1.4 (v2.2.0):
# [NOISE] Gaussian noise injected at write-time on every numeric channel.
#         Sigma = 1% of rolling-window std (last 300 steps) per channel.
# [SPIKE] Rare 5-10 sigma outlier spikes on every numeric channel.
#         Probability: 0.5% per tick per channel (independent).
# [DROP]  Occasional sensor dropouts written as empty string (null in CSV).
#         Probability: 0.5% per sensor group per tick.
#         Groups and their propagation chains:
#           - IMU group    : imu_lin_acc_x/y/z, imu_ang_vel_x/y/z,
#                            vibration_magnitude
#           - DRIVE group  : drive_joint_velocity, drive_joint_effort
#                            (also nulls power_dissipated_w, temperature_c)
#           - LIFT group   : lift_joint_position, lift_joint_velocity,
#                            lift_force_z, pseudo_pressure_pa
#                            (also nulls power_dissipated_w, temperature_c)
#           - ROLLER_FL/FR/BL/BR : individual roller_*_velocity channels
#         power_dissipated_w and temperature_c go null if EITHER drive OR
#         lift group drops. timestamp_s, step_index, fault_label always written.
#
# NOTE: fault_label, FAULT_SEQUENCE, and all fault-physics are managed
#       entirely by the scenario writer. This script does not modify them.
# =============================================================================

import csv
import os
from collections import deque
from datetime import datetime

import carb
import numpy as np
import omni.kit.app
import omni.physx
import omni.timeline
import omni.usd

from omni.isaac.core import World
from isaacsim.core.prims import SingleArticulation
from isaacsim.sensors.physics import IMUSensor
from pxr import UsdPhysics, PhysxSchema

# =============================================================================
# CONFIG
# =============================================================================
FORKLIFT_ROOT   = "/World/forklift_b_sensor"
IMU_PRIM_PATH   = "/World/forklift_b_sensor/body/sensors/hawk_front/Imu_Sensor"
CSV_OUTPUT_DIR  = "C:/IsaacStages/bitirme/DTX_recordings"
PHYSICS_RATE_HZ = 60.0

THERMAL_ALPHA   = 0.00077778  # v2.13: yeniden hesaplandı — tau=5s, ss_nominal=32°C @ 1800W
                               # formül: ALPHA = BETA*(T_target - T_amb)/P_nom = 0.2*(32-25)/1800
THERMAL_BETA    = 0.2          # v2.13: 1/(60*60)→0.2 (tau=5s); 3tau=15s → 25s pencerede doyum ✓
THERMAL_T_AMB   = 25.0                         # ambient temperature (°C)
CONTACT_AREA_M2 = 0.08                         # lift cylinder contact area for pseudo-pressure
WARMUP_STEPS    = 10                           # steps discarded before recording starts
FREEZE_STEPS    = 3                            # consecutive steps with no velocity change → freeze guard
FREEZE_EPS      = 1e-6
THERMAL_MAX_C   = 90.0   # v2.12: 45→90; overheat fault beta*0.05 → steady-state ~72°C (>45°C ✓)
POWER_SPIKE_MAX = 5000.0                       # max power fed to thermal integrator (W); raw value still written to CSV

# Noise / spike / dropout
NOISE_ROLLING_WINDOW = 300      # rolling window length in steps (~5 s at 60 Hz)
NOISE_SIGMA_FRACTION = 0.01     # noise sigma = 1% of rolling std per channel
SPIKE_PROB           = 0.005    # probability of a spike event per tick per channel
SPIKE_SIGMA_LOW      = 5.0      # spike magnitude range (multiples of sigma)
SPIKE_SIGMA_HIGH     = 10.0
DROPOUT_PROB         = 0.005    # probability of a group dropout per tick
TEMP_DROPOUT_PROB    = 0.001    # independent dropout prob for temperature_c only (0.1% per tick)
                                # Real thermal sensors don't null out with joint encoder dropouts.
SPIKE_EXEMPT         = {"temperature_c", "power_dissipated_w"}
                                # Derived/integrator channels excluded from spike injection.
                                # Spikes on these are physically nonsensical and corrupt ML labels.
FLUSH_INTERVAL_STEPS = 300      # flush CSV to disk every N steps (~5 s at 60 Hz)
# =============================================================================

# Empty string sentinel written to CSV for dropped (null) values; pandas reads as NaN.
_NULL = ""

# Ordered list of numeric column names matching CSV header (excludes timestamp_s,
# step_index, fault_label). Used to allocate one _RollingStats buffer per channel.
_NUMERIC_COLS = [
    "imu_lin_acc_x", "imu_lin_acc_y", "imu_lin_acc_z",
    "imu_ang_vel_x", "imu_ang_vel_y", "imu_ang_vel_z",
    "vibration_magnitude",
    "lift_joint_position",
    "lift_force_z", "pseudo_pressure_pa",
    "drive_joint_velocity", "drive_joint_effort",
    "lift_joint_velocity",
    "roller_fl_velocity", "roller_fr_velocity",
    "roller_bl_velocity", "roller_br_velocity",
    "power_dissipated_w", "temperature_c",
]

# Sensor bus topology for dropout simulation. Each group drops together as a unit.
# power_dissipated_w and temperature_c are handled separately (cascade from drive+lift).
_DROPOUT_GROUPS = {
    "imu":       ["imu_lin_acc_x", "imu_lin_acc_y", "imu_lin_acc_z",
                  "imu_ang_vel_x", "imu_ang_vel_y", "imu_ang_vel_z",
                  "vibration_magnitude"],
    "drive":     ["drive_joint_velocity", "drive_joint_effort"],
    "lift":      ["lift_joint_position", "lift_joint_velocity",
                  "lift_force_z", "pseudo_pressure_pa"],
    "roller_fl": ["roller_fl_velocity"],
    "roller_fr": ["roller_fr_velocity"],
    "roller_bl": ["roller_bl_velocity"],
    "roller_br": ["roller_br_velocity"],
}


# =============================================================================

def _apply_mbp_broadphase():
    """Switch the PhysicsScene broadphase to MBP to avoid TGS solver warnings."""
    try:
        stage = omni.usd.get_context().get_stage()
        scene_path = None
        for prim in stage.Traverse():
            if prim.IsA(UsdPhysics.Scene):
                scene_path = str(prim.GetPath())
                break
        if scene_path is None:
            carb.log_warn("[DTX] No PhysicsScene found.")
            return
        prim = stage.GetPrimAtPath(scene_path)
        api  = PhysxSchema.PhysxSceneAPI.Apply(prim)
        api.CreateBroadphaseTypeAttr().Set("MBP")
        carb.log_warn("[DTX] Broadphase set to MBP: " + scene_path)
    except Exception as exc:
        carb.log_warn("[DTX] MBP fix skipped: " + str(exc))


def _read_drive_params(stage, joint_path):
    """Read stiffness and damping from PhysicsDriveAPI:linear on the lift joint."""
    try:
        prim      = stage.GetPrimAtPath(joint_path)
        drive     = UsdPhysics.DriveAPI.Get(prim, "linear")
        stiffness = drive.GetStiffnessAttr().Get()
        damping   = drive.GetDampingAttr().Get()
        stiffness = float(stiffness) if stiffness is not None else 0.0
        damping   = float(damping)   if damping   is not None else 0.0
        carb.log_warn("[DTX] Lift drive stiffness=" + str(stiffness) +
                      " damping=" + str(damping))
        return stiffness, damping
    except Exception as exc:
        carb.log_warn("[DTX] Could not read drive params: " + str(exc) +
                      " -- using 0.0")
        return 0.0, 0.0


def _read_drive_target(stage, joint_path):
    """Read the current targetPosition from PhysicsDriveAPI:linear."""
    try:
        prim   = stage.GetPrimAtPath(joint_path)
        drive  = UsdPhysics.DriveAPI.Get(prim, "linear")
        target = drive.GetTargetPositionAttr().Get()
        return float(target) if target is not None else 0.0
    except Exception:
        return 0.0


# =============================================================================
# FAULT_SEQUENCE — managed entirely by the scenario writer.
# This script reads it but never modifies it.
# =============================================================================
FAULT_SEQUENCE = [
    # Tur 1 — train seti  (her pencere 30s; bearing_wear ve pressure_fault extra uzun)
    (  0,  30, "nominal"),
    ( 30,  60, "overload"),
    ( 60,  85, "overheat"),          # 25s — hızlı doyum, fazlası yeterli
    ( 85, 120, "pressure_fault"),    # 35s — daha fazla satır
    (120, 155, "bearing_wear"),      # 35s — daha fazla satır
    (155, 185, "wheel_slip"),        # 30s
    # Tur 2 — train seti (farklı sıra)
    (185, 215, "nominal"),
    (215, 250, "bearing_wear"),      # 35s
    (250, 280, "wheel_slip"),
    (280, 310, "overload"),
    (310, 345, "pressure_fault"),    # 35s
    (345, 370, "overheat"),          # 25s
    # Tur 3 — test seti
    (370, 400, "nominal"),
    (400, 425, "overheat"),          # 25s
    (425, 455, "overload"),
    (455, 485, "wheel_slip"),
    (485, 520, "bearing_wear"),      # 35s
    (520, 555, "pressure_fault"),    # 35s
    # Tur 4 — ek buffer
    (555, 585, "nominal"),
    (585, 610, "overheat"),          # 25s
    (610, 645, "bearing_wear"),      # 35s
    (645, 675, "overload"),
    (675, 705, "wheel_slip"),
    (705, 740, "pressure_fault"),    # 35s
]


# =============================================================================
# Rolling statistics accumulator
# =============================================================================
class _RollingStats:
    """Incremental rolling-window mean and std backed by a fixed-size deque.

    Uses running sum / sum-of-squares so std is O(1) per update with no
    per-step numpy allocation. One instance is created per numeric column
    and reset on every PLAY.
    """

    def __init__(self, window: int):
        self._window = window
        self._buf    = deque(maxlen=window)
        self._sum    = 0.0
        self._sum_sq = 0.0

    def update(self, value: float):
        if len(self._buf) == self._window:
            old = self._buf[0]
            self._sum    -= old
            self._sum_sq -= old * old
        self._buf.append(value)
        self._sum    += value
        self._sum_sq += value * value

    @property
    def n(self) -> int:
        return len(self._buf)

    @property
    def mean(self) -> float:
        if self.n == 0:
            return 0.0
        return self._sum / self.n

    @property
    def std(self) -> float:
        if self.n < 2:
            return 0.0
        variance = (self._sum_sq - self._sum * self._sum / self.n) / (self.n - 1)
        return float(np.sqrt(max(variance, 0.0)))


# =============================================================================
# Main logger
# =============================================================================
class DTXSensorLogger:

    def __init__(self):
        self._art             = None
        self._imu             = None
        self._csv_file        = None
        self._csv_writer      = None
        self._csv_path        = ""
        self._recording       = False
        self._step_count      = 0
        self._temperature     = THERMAL_T_AMB
        self._prev_vel        = None
        self._freeze_count    = 0
        self._idx_drive       = None
        self._idx_lift        = None
        self._idx_rollers     = {}
        self._physics_sub     = None
        self._was_playing     = False
        self._lift_stiffness  = 0.0
        self._lift_damping    = 0.0
        self._lift_joint_path = ""
        self._fault_label     = ""

        # One rolling stats buffer per numeric column; reset on every PLAY.
        self._rolling: dict[str, _RollingStats] = {
            col: _RollingStats(NOISE_ROLLING_WINDOW) for col in _NUMERIC_COLS
        }

        self._rng = np.random.default_rng()

        # --- Fault physics state (managed by _scenario_tick) ---
        # Nominal (baseline) values read once at PLAY; restored on fault exit.
        self._nominal_drive_damping   = None   # float — back_wheel_drive angular damping
        self._nominal_thermal_beta    = THERMAL_BETA
        self._thermal_beta            = THERMAL_BETA  # v2.14: explicit init — _scenario_tick'ten önce de kullanılabilir
        self._nominal_ground_friction = None   # float — ground PhysicsMaterial dynamic friction
        self._nominal_lift_upper      = None   # float — lift_joint upper limit (m)
        self._payload_prim_path       = FORKLIFT_ROOT + "/forks/dtx_payload_mass"
        self._payload_added           = False
        # Current active fault label used by _scenario_tick (separate from logger label)
        self._active_physics_fault    = ""
        # Ramp tracking: (fault_label, ramp_start_s, ramp_end_s, direction)
        # direction: "in" = nominal→fault, "out" = fault→nominal
        self._ramp_state              = None
        # Drive joint path for damping manipulation
        self._drive_joint_path        = FORKLIFT_ROOT + "/back_wheel_joints/back_wheel_drive"
        # Ground material prim path (set during _on_play)
        self._ground_material_path    = ""

        self._app_sub = omni.kit.app.get_app().get_update_event_stream() \
            .create_subscription_to_pop(self._on_app_update,
                                        name="dtx_app_update")

        carb.log_warn("[DTX] ==================================================")
        carb.log_warn("[DTX] DTX-AI Forklift Sensor Logger v2.17.0")
        carb.log_warn("[DTX] Isaac Sim 4.5 | github.com/YKesX/DTX-AI")
        carb.log_warn("[DTX] ==================================================")
        carb.log_warn("[DTX] Root  : " + FORKLIFT_ROOT)
        carb.log_warn("[DTX] IMU   : " + IMU_PRIM_PATH)
        carb.log_warn("[DTX] Output: " + CSV_OUTPUT_DIR)
        carb.log_warn("[DTX] Rate  : " + str(PHYSICS_RATE_HZ) + " Hz")
        carb.log_warn("[DTX] Noise : sigma=" + str(NOISE_SIGMA_FRACTION * 100) +
                      "% rolling-" + str(NOISE_ROLLING_WINDOW) + "-step std")
        carb.log_warn("[DTX] Spike : p=" + str(SPIKE_PROB) + " / " +
                      str(SPIKE_SIGMA_LOW) + "-" + str(SPIKE_SIGMA_HIGH) + "\u03c3")
        carb.log_warn("[DTX] Drop  : p=" + str(DROPOUT_PROB) + " per group")
        carb.log_warn("[DTX] Ready. Press PLAY.")
        carb.log_warn("[DTX] ==================================================")

    # ------------------------------------------------------------------
    # App update: detect PLAY / STOP transitions
    # ------------------------------------------------------------------
    def _on_app_update(self, event):
        tl      = omni.timeline.get_timeline_interface()
        playing = tl.is_playing()
        if playing and not self._was_playing:
            self._was_playing = True
            self._on_play()
        elif not playing and self._was_playing:
            self._was_playing = False
            self._on_stop()

    # ------------------------------------------------------------------
    # PLAY
    # ------------------------------------------------------------------
    def _on_play(self):
        if self._recording:
            return
        carb.log_warn("[DTX] PLAY -- initialising...")
        _apply_mbp_broadphase()

        self._world = World.instance() or World(stage_units_in_meters=1.0)

        # Attach to the existing IMU prim — do NOT call IMUSensor() with create=True.
        self._imu = IMUSensor(prim_path=IMU_PRIM_PATH)
        self._imu.initialize()
        omni.kit.app.get_app().update()
        carb.log_warn("[DTX] IMU ready.")

        self._art = SingleArticulation(prim_path=FORKLIFT_ROOT, name="dtx_art")
        self._art.initialize()
        names = list(self._art.dof_names)
        carb.log_warn("[DTX] DOFs: " + str(names))

        def find(kw):
            for i, n in enumerate(names):
                if kw in n:
                    return i
            return None

        self._idx_drive   = find("back_wheel_drive")
        self._idx_lift    = find("lift_joint")
        self._idx_rollers = {
            "fl": find("front_left_roller"),
            "fr": find("front_right_roller"),
            "bl": find("back_left_roller"),
            "br": find("back_right_roller"),
        }

        self._lift_joint_path = FORKLIFT_ROOT + "/lift_joint"
        stage = omni.usd.get_context().get_stage()
        self._lift_stiffness, self._lift_damping = _read_drive_params(
            stage, self._lift_joint_path)

        # --- Read nominal physics values for fault physics manipulation ---
        # 1) back_wheel_drive angular damping
        try:
            drive_prim  = stage.GetPrimAtPath(self._drive_joint_path)
            drive_api   = UsdPhysics.DriveAPI.Get(drive_prim, "angular")
            damp_attr   = drive_api.GetDampingAttr()
            self._nominal_drive_damping = float(damp_attr.Get() or 0.0)
        except Exception as exc:
            carb.log_warn("[DTX] Could not read drive damping: " + str(exc))
            self._nominal_drive_damping = 0.0

        # 2) thermal beta (always reset from module constant)
        self._nominal_thermal_beta = THERMAL_BETA
        self._thermal_beta         = THERMAL_BETA   # mutable copy used in physics step

        # 3) ground material dynamic friction
        self._ground_material_path = ""
        try:
            for prim in stage.Traverse():
                # PhysicsMaterialAPI uygulanmış prim'i ara
                # MaterialAPI.Get(prim) C++ type mismatch veriyor — doğrudan attribute'a bak
                path_str = str(prim.GetPath())
                if any(kw in path_str.lower() for kw in ("ground", "floor", "physmat", "concrete")):
                    dyn_attr = prim.GetAttribute("physics:dynamicFriction")
                    if dyn_attr and dyn_attr.IsValid():
                        self._ground_material_path    = path_str
                        self._nominal_ground_friction = float(dyn_attr.Get() or 0.8)
                        carb.log_warn("[DTX] Ground material found: " + path_str +
                                      " friction=" + str(self._nominal_ground_friction))
                        break
            if not self._ground_material_path:
                carb.log_warn("[DTX] Ground material not found — wheel_slip uses roller damping fallback.")
                self._nominal_ground_friction = 0.8
        except Exception as exc:
            carb.log_warn("[DTX] Ground material search error: " + str(exc))
            self._nominal_ground_friction = 0.8

        # 4) lift joint upper limit
        try:
            from pxr import UsdPhysics as _UP2
            lift_prim   = stage.GetPrimAtPath(self._lift_joint_path)
            linear_api  = _UP2.PrismaticJoint(lift_prim)
            upper_attr  = linear_api.GetUpperLimitAttr()
            self._nominal_lift_upper = float(upper_attr.Get() if upper_attr.Get() is not None else 1e6)
        except Exception as exc:
            carb.log_warn("[DTX] Could not read lift upper limit: " + str(exc))
            self._nominal_lift_upper = 1e6

        # Reset fault physics state
        self._active_physics_fault = ""
        self._ramp_state           = None
        self._payload_added        = False
        self._thermal_beta         = THERMAL_BETA   # v2.14: her PLAY'de nominal'e sıfırla
        carb.log_warn("[DTX] Nominal physics — drive_damping=" + str(self._nominal_drive_damping) +
                      " lift_upper=" + str(self._nominal_lift_upper))

        self._step_count   = 0
        self._temperature  = THERMAL_T_AMB
        self._prev_vel     = None
        self._freeze_count = 0

        for stats in self._rolling.values():
            stats._buf.clear()
            stats._sum    = 0.0
            stats._sum_sq = 0.0

        os.makedirs(CSV_OUTPUT_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._csv_path   = os.path.join(CSV_OUTPUT_DIR, "dtx_" + ts + ".csv")
        self._csv_file   = open(self._csv_path, "w", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow([
            "timestamp_s", "step_index",
            "imu_lin_acc_x", "imu_lin_acc_y", "imu_lin_acc_z",
            "imu_ang_vel_x", "imu_ang_vel_y", "imu_ang_vel_z",
            "vibration_magnitude",
            "lift_joint_position",
            "lift_force_z", "pseudo_pressure_pa",
            "drive_joint_velocity", "drive_joint_effort",
            "lift_joint_velocity",
            "roller_fl_velocity", "roller_fr_velocity",
            "roller_bl_velocity", "roller_br_velocity",
            "power_dissipated_w", "temperature_c",
            "fault_label",
        ])

        self._recording = True
        carb.log_warn("[DTX] Recording: " + self._csv_path)

        def _deferred_subscribe(event):
            try:
                self._physics_sub = \
                    omni.physx.get_physx_interface().subscribe_physics_step_events(
                        self._on_physics_step)
                carb.log_warn("[DTX] Physics subscription active.")
            except Exception as exc:
                carb.log_warn("[DTX] Physics subscribe error: " + str(exc))
            self._deferred_sub = None

        self._deferred_sub = omni.kit.app.get_app().get_update_event_stream() \
            .create_subscription_to_pop_by_type(
                0, _deferred_subscribe,
                name="dtx_deferred_physics", order=100)

    # ------------------------------------------------------------------
    # PHYSICS STEP
    # ------------------------------------------------------------------
    def _on_physics_step(self, dt):
        if not self._recording:
            return

        self._step_count += 1
        if self._step_count <= WARMUP_STEPS:
            return

        sim_time = self._step_count / PHYSICS_RATE_HZ

        self._fault_label = ""
        for (start_s, end_s, label) in FAULT_SEQUENCE:
            if start_s <= sim_time < end_s:
                self._fault_label = label
                break

        # --- IMU ---
        try:
            frame   = self._imu.get_current_frame()
            lin_acc = np.array(frame["lin_acc"], dtype=float)
            ang_vel = np.array(frame["ang_vel"], dtype=float)
        except Exception:
            lin_acc = np.zeros(3)
            ang_vel = np.zeros(3)

        vib_mag = float(np.linalg.norm(lin_acc))

        # --- Articulation ---
        try:
            vels     = self._art.get_joint_velocities()
            pos      = self._art.get_joint_positions()
            measured = self._art.get_measured_joint_forces()

            def vel(i):
                if i is None: return 0.0
                return float(vels[0, i]) if vels.ndim == 2 else float(vels[i])

            def position(i):
                if i is None: return 0.0
                return float(pos[0, i]) if pos.ndim == 2 else float(pos[i])

            def force_fz(i):
                if i is None: return 0.0
                row = measured[0, i] if measured.ndim == 3 else measured[i]
                if hasattr(row, "__len__") and len(row) > 2:
                    return float(row[2])
                return float(row)

            drive_vel    = vel(self._idx_drive)
            drive_effort = force_fz(self._idx_drive)
            lift_pos     = position(self._idx_lift)
            lift_vel     = vel(self._idx_lift)

            applied = self._art.get_applied_joint_efforts()

            def ga(i):
                if i is None: return 0.0
                val = applied[0, i] if applied.ndim == 2 else applied[i]
                return float(val)

            lift_force_applied = ga(self._idx_lift)

            # lift_joint uses PhysicsDriveAPI:linear; get_applied_joint_efforts()
            # returns the real solver drive force in N/cm (asset authored in cm).
            # Divide by 100 to convert to SI Newtons. When the joint is at rest
            # (applied ≈ 0) fall back to the damping-velocity proxy.
            if abs(lift_force_applied) < 1e-6:
                lift_vel_cms = lift_vel * 100.0
                lift_force   = float(np.clip(
                    (self._lift_damping * (-lift_vel_cms)) / 100.0,
                    -15000.0, 15000.0))
            else:
                lift_force = float(np.clip(
                    lift_force_applied / 100.0, -15000.0, 15000.0))

            rv_fl = vel(self._idx_rollers["fl"])
            rv_fr = vel(self._idx_rollers["fr"])
            rv_bl = vel(self._idx_rollers["bl"])
            rv_br = vel(self._idx_rollers["br"])

        except Exception as exc:
            carb.log_warn("[DTX] Articulation error: " + str(exc))
            drive_vel = drive_effort = 0.0
            lift_pos  = lift_vel = lift_force = 0.0
            rv_fl     = rv_fr = rv_bl = rv_br = 0.0

        pseudo_pressure = (lift_force / CONTACT_AREA_M2
                           if CONTACT_AREA_M2 > 0 else 0.0)

        # Freeze guard: suppress power when drive velocity is unchanged for
        # FREEZE_STEPS consecutive steps (PhysX solver stall artefact).
        if (self._prev_vel is not None and
                abs(drive_vel - self._prev_vel) < FREEZE_EPS):
            self._freeze_count += 1
        else:
            self._freeze_count = 0
        self._prev_vel = drive_vel

        # v2.14: Thermal input = drive_effort^2 proxy (effort always present even at DRIVE_STOP).
        # vel*effort drops to 0 during stop phases → integratör soğuyor, fault bantları kayboluyor.
        # effort^2 / EFFORT_THERMAL_SCALE → ~1800W nominal seviyesine normalize edilmiş.
        EFFORT_THERMAL_SCALE = 4769.0  # effort_mean≈2930 → 2930^2/4769 ≈ 1800W ≈ nominal
        effort_power = (drive_effort * drive_effort) / EFFORT_THERMAL_SCALE
        eff_power    = effort_power if self._freeze_count < FREEZE_STEPS else 0.0
        # power_dissipated_w CSV kolonu için orijinal vel*effort korunuyor (ML feature olarak faydalı)
        power_w   = abs(drive_vel * drive_effort)

        # Clamp power entering the thermal integrator to reject non-physical
        # single-frame impulses (teleport, external force). The raw power_w
        # is still written to CSV so the spike remains visible in the data.
        # NOTE: self._thermal_beta is modified by the overheat fault physics.
        # Scale by dt*PHYSICS_RATE_HZ so integration is rate-independent;
        # at nominal 60 Hz dt_scale≈1.0, but corrects if sim runs slower.
        # v2.15 FIX: scenario_tick ÖNCE → beta güncellenir → integratör yeni beta ile çalışır
        self._scenario_tick(dt)

        thermal_input = min(eff_power, POWER_SPIKE_MAX)
        dt_scale = dt * PHYSICS_RATE_HZ
        self._temperature += dt_scale * (
            THERMAL_ALPHA * thermal_input
            - self._thermal_beta * (self._temperature - THERMAL_T_AMB)
        )
        self._temperature = min(self._temperature, THERMAL_MAX_C)

        # --- Build clean (pre-noise) value dict ---
        clean = {
            "imu_lin_acc_x":       lin_acc[0],
            "imu_lin_acc_y":       lin_acc[1],
            "imu_lin_acc_z":       lin_acc[2],
            "imu_ang_vel_x":       ang_vel[0],
            "imu_ang_vel_y":       ang_vel[1],
            "imu_ang_vel_z":       ang_vel[2],
            "vibration_magnitude": vib_mag,
            "lift_joint_position": lift_pos,
            "lift_force_z":        lift_force,
            "pseudo_pressure_pa":  pseudo_pressure,
            "drive_joint_velocity": drive_vel,
            "drive_joint_effort":  drive_effort,
            "lift_joint_velocity": lift_vel,
            "roller_fl_velocity":  rv_fl,
            "roller_fr_velocity":  rv_fr,
            "roller_bl_velocity":  rv_bl,
            "roller_br_velocity":  rv_br,
            "power_dissipated_w":  eff_power,
            "temperature_c":       self._temperature,
        }

        # Update rolling stats with clean values (noise sigma derived from these).
        for col, val in clean.items():
            self._rolling[col].update(val)

        # --- v2.16: Fault signal injection (physics manipülasyonu yetersiz kalan faultlar) ---
        # Isaac Sim'de bazı parametreler (damping, lift_upper) sensör okumasını
        # yeterince etkilemiyor. Gerçekçi ayrışım için doğrudan sinyal pertürbasyon ekliyoruz.
        active_fault = self._active_physics_fault
        _t = self._step_count / PHYSICS_RATE_HZ  # simulation time for oscillations

        if active_fault == "bearing_wear":
            # Rulman hasarı: yüksek frekanslı titreşim + artan effort proxy
            bw_vib_amp = 3.5        # m/s² ek titreşim genliği
            bw_freq    = 12.0       # Hz — rulman pass frekansı
            bw_osc     = bw_vib_amp * np.sin(2 * np.pi * bw_freq * _t)
            clean["imu_lin_acc_x"]    += bw_osc
            clean["imu_lin_acc_y"]    += bw_osc * 0.6
            clean["vibration_magnitude"] = float(np.linalg.norm([
                clean["imu_lin_acc_x"], clean["imu_lin_acc_y"], clean["imu_lin_acc_z"]]))
            clean["drive_joint_effort"]  *= 1.55   # %55 artış — rulman sürtünmesi

        elif active_fault == "overload":
            # Aşırı yük: lift kanallarında ağırlık etkisi
            clean["lift_force_z"]       -= 3500.0   # N ek yük (500 kg × 9.8 / 1.4)
            clean["pseudo_pressure_pa"] = clean["lift_force_z"] / CONTACT_AREA_M2
            clean["drive_joint_effort"] *= 1.25     # yük altında artan çekiş

        elif active_fault == "pressure_fault":
            # Hidrolik basınç hatası: basınç düşüşü + lift instabilitesi
            # Amplitude artırıldı — gürültü sinyali bastırmasın
            clean["lift_force_z"]       *= 0.25     # daha derin basınç kaybı (0.45→0.25)
            clean["pseudo_pressure_pa"] = clean["lift_force_z"] / CONTACT_AREA_M2
            pf_flutter = 1800.0 * np.sin(2 * np.pi * 2.0 * _t)  # 2 Hz titreme, 2× amplitude
            clean["lift_force_z"]       += pf_flutter
            clean["pseudo_pressure_pa"] += pf_flutter / CONTACT_AREA_M2

        elif active_fault == "wheel_slip":
            # Tekerlek kayması: roller hızı drive hızından sapıyor (overspeed)
            slip_factor = 2.8       # roller × 2.8 → kayma belirgin
            clean["roller_fl_velocity"] = clean["drive_joint_velocity"] * slip_factor
            clean["roller_fr_velocity"] = clean["drive_joint_velocity"] * slip_factor
            clean["roller_bl_velocity"] = clean["drive_joint_velocity"] * slip_factor
            clean["roller_br_velocity"] = clean["drive_joint_velocity"] * slip_factor
            # Drive effort düşer (zemin tutuşu yok)
            clean["drive_joint_effort"] *= 0.55

        # --- Inject Gaussian noise + rare spikes ---
        noised = {}
        for col, val in clean.items():
            stats = self._rolling[col]
            sigma = stats.std * NOISE_SIGMA_FRACTION if stats.n >= 2 else 0.0
            noise = self._rng.normal(0.0, sigma) if sigma > 0.0 else 0.0

            # Spike injection is skipped for derived/integrator channels
            # (temperature_c, power_dissipated_w) — spikes on these are
            # physically nonsensical and corrupt ML fault labels.
            if col not in SPIKE_EXEMPT and self._rng.random() < SPIKE_PROB:
                spike_sigma = self._rng.uniform(SPIKE_SIGMA_LOW, SPIKE_SIGMA_HIGH)
                spike_sign  = self._rng.choice([-1.0, 1.0])
                # Fall back to 1% of |value| as sigma when channel has no variance yet.
                noise += spike_sign * spike_sigma * (sigma if sigma > 0.0
                                                     else abs(val) * 0.01 + 1e-9)
            noised[col] = val + noise

        # --- Apply sensor group dropouts ---
        dropped_groups = set()
        for group_key in _DROPOUT_GROUPS:
            if self._rng.random() < DROPOUT_PROB:
                dropped_groups.add(group_key)

        out = dict(noised)
        for group_key, cols in _DROPOUT_GROUPS.items():
            if group_key in dropped_groups:
                for col in cols:
                    out[col] = _NULL

        # power_dissipated_w is derived from both drive and lift;
        # null either source group and power goes null too.
        # temperature_c is NOT cascaded from joint dropouts — a real thermal
        # sensor does not lose signal when a joint encoder drops. Instead it
        # has its own independent low-probability dropout.
        if "drive" in dropped_groups or "lift" in dropped_groups:
            out["power_dissipated_w"] = _NULL
        if self._rng.random() < TEMP_DROPOUT_PROB:
            out["temperature_c"] = _NULL

        # --- Write CSV row ---
        def fmt(col, decimals=6):
            v = out[col]
            if v is _NULL:
                return _NULL
            fv = float(v)
            if col == "power_dissipated_w":
                fv = max(fv, 0.0)  # noise can push near-zero power negative; clamp at write-time
            return round(fv, decimals)

        self._csv_writer.writerow([
            round(sim_time, 6),   self._step_count,
            fmt("imu_lin_acc_x"), fmt("imu_lin_acc_y"), fmt("imu_lin_acc_z"),
            fmt("imu_ang_vel_x"), fmt("imu_ang_vel_y"), fmt("imu_ang_vel_z"),
            fmt("vibration_magnitude"),
            fmt("lift_joint_position"),
            fmt("lift_force_z"),  fmt("pseudo_pressure_pa", decimals=4),
            fmt("drive_joint_velocity"), fmt("drive_joint_effort"),
            fmt("lift_joint_velocity"),
            fmt("roller_fl_velocity"), fmt("roller_fr_velocity"),
            fmt("roller_bl_velocity"), fmt("roller_br_velocity"),
            fmt("power_dissipated_w"), fmt("temperature_c", decimals=4),
            self._fault_label,
        ])

        # Flush CSV periodically to prevent data loss on crash or forced stop.
        if self._step_count % FLUSH_INTERVAL_STEPS == 0:
            self._csv_file.flush()

    # ------------------------------------------------------------------
    # STOP
    # ------------------------------------------------------------------
    def _on_stop(self):
        if not self._recording:
            return
        self._recording = False
        # --- Restore all fault physics to nominal before stopping ---
        try:
            stage = omni.usd.get_context().get_stage()
            if self._nominal_drive_damping is not None:
                prim  = stage.GetPrimAtPath(self._drive_joint_path)
                drive = UsdPhysics.DriveAPI.Get(prim, "angular")
                if drive:
                    drive.GetDampingAttr().Set(self._nominal_drive_damping)
            self._thermal_beta = self._nominal_thermal_beta
            if self._ground_material_path and self._nominal_ground_friction is not None:
                prim     = stage.GetPrimAtPath(self._ground_material_path)
                dyn_attr = prim.GetAttribute("physics:dynamicFriction")
                sta_attr = prim.GetAttribute("physics:staticFriction")
                if dyn_attr and dyn_attr.IsValid():
                    dyn_attr.Set(self._nominal_ground_friction)
                if sta_attr and sta_attr.IsValid():
                    sta_attr.Set(self._nominal_ground_friction + 0.1)
            if self._nominal_lift_upper is not None:
                from pxr import UsdPhysics as _UPstop2
                prim2 = stage.GetPrimAtPath(self._lift_joint_path)
                _UPstop2.PrismaticJoint(prim2).GetUpperLimitAttr().Set(self._nominal_lift_upper)
            if self._payload_added:
                stage.RemovePrim(self._payload_prim_path)
                self._payload_added = False
            carb.log_warn("[DTX] Fault physics restored to nominal.")
        except Exception as exc:
            carb.log_warn("[DTX] Cleanup warning: " + str(exc))
        # --- Close CSV ---
        if self._physics_sub:
            self._physics_sub.unsubscribe()
            self._physics_sub = None
        if self._csv_file:
            self._csv_file.flush()
            self._csv_file.close()
            self._csv_file   = None
            self._csv_writer = None
        steps = max(0, self._step_count - WARMUP_STEPS)
        carb.log_warn("[DTX] Saved : " + self._csv_path)
        carb.log_warn("[DTX] Steps : " + str(steps))

    def _scenario_tick(self, dt: float):
        """v2.10: Sınıf metodu. _on_physics_step her adımda çağırır."""
        if not self._recording:
            return

        current_time = self._step_count / PHYSICS_RATE_HZ
        stage        = omni.usd.get_context().get_stage()

        RAMP_IN  = 2.0   # v2.14: 5→2s; geçiş süresi kısa, boş label azalır
        RAMP_OUT = 2.0   # v2.14: 5→2s

        # 1. Fault sequence'den aktif label bul
        target_label = ""
        for (start_s, end_s, label) in FAULT_SEQUENCE:
            if start_s <= current_time < end_s:
                target_label = label
                break

        self._fault_label = target_label

        # 2. Geçiş tespiti
        prev_fault = self._active_physics_fault
        if target_label != prev_fault:
            self._ramp_state           = (target_label, current_time)
            self._active_physics_fault = target_label
            if prev_fault:
                carb.log_warn("[SCENARIO] " + prev_fault + " → " + (target_label or "nominal"))
            else:
                carb.log_warn("[SCENARIO] Fault enter: " + target_label +
                              " at t=" + str(round(current_time, 1)))

        # 3. Ramp fraction
        ramp_frac = 0.0
        if self._ramp_state is not None:
            ramp_label, ramp_start = self._ramp_state
            elapsed = current_time - ramp_start
            if ramp_label == "" or ramp_label != target_label:
                ramp_frac = max(0.0, 1.0 - elapsed / RAMP_OUT)
                if ramp_frac <= 0.0:
                    self._ramp_state           = None
                    self._active_physics_fault = ""
            else:
                ramp_frac = min(1.0, elapsed / RAMP_IN)

        active = self._active_physics_fault

        # Helpers
        def _set_drive_damping(value):
            try:
                prim  = stage.GetPrimAtPath(self._drive_joint_path)
                drive = UsdPhysics.DriveAPI.Get(prim, "angular")
                if drive:
                    drive.GetDampingAttr().Set(value)
            except Exception as exc:
                carb.log_warn("[SCENARIO] damping set error: " + str(exc))

        def _set_lift_upper(value):
            try:
                from pxr import UsdPhysics as _UP2
                prim = stage.GetPrimAtPath(self._lift_joint_path)
                _UP2.PrismaticJoint(prim).GetUpperLimitAttr().Set(value)
            except Exception as exc:
                carb.log_warn("[SCENARIO] lift upper set error: " + str(exc))

        def _ensure_payload(add):
            if add and not self._payload_added:
                try:
                    from pxr import UsdGeom, UsdPhysics as _UP3, Gf
                    xform = UsdGeom.Xform.Define(stage, self._payload_prim_path)
                    xform.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0.1))
                    _UP3.MassAPI.Apply(xform.GetPrim()).GetMassAttr().Set(500.0)
                    self._payload_added = True
                    carb.log_warn("[SCENARIO] Payload 500kg eklendi.")
                except Exception as exc:
                    carb.log_warn("[SCENARIO] payload add error: " + str(exc))
            elif not add and self._payload_added:
                try:
                    stage.RemovePrim(self._payload_prim_path)
                    self._payload_added = False
                    carb.log_warn("[SCENARIO] Payload kaldırıldı.")
                except Exception as exc:
                    carb.log_warn("[SCENARIO] payload remove error: " + str(exc))

        # 4. Fault fizikleri
        nom_damp = self._nominal_drive_damping
        nom_beta = self._nominal_thermal_beta

        FAULT_DRIVE_DAMPING_DELTA = 15000.0  # bearing_wear: nominal≈10000 → 25000 → P≈2×nominal → ss≈39°C
        FAULT_THERMAL_BETA_RATIO  = 0.05     # overheat: beta*0.05 → 25s'de ~60°C (tau=5s ile ✓)

        if active == "bearing_wear":
            lerped = nom_damp + (nom_damp + FAULT_DRIVE_DAMPING_DELTA - nom_damp) * ramp_frac
            _set_drive_damping(lerped)
            self._thermal_beta = nom_beta
            _ensure_payload(False)
            _set_lift_upper(self._nominal_lift_upper)

        elif active == "overheat":
            target_beta = nom_beta * FAULT_THERMAL_BETA_RATIO
            self._thermal_beta = nom_beta + (target_beta - nom_beta) * ramp_frac
            _set_drive_damping(nom_damp)
            _ensure_payload(False)
            _set_lift_upper(self._nominal_lift_upper)

        elif active == "overload":
            _ensure_payload(ramp_frac >= 0.5)
            self._thermal_beta = nom_beta
            _set_drive_damping(nom_damp)
            _set_lift_upper(self._nominal_lift_upper)

        elif active == "pressure_fault":
            if ramp_frac >= 0.5:
                try:
                    pos = self._art.get_joint_positions() if self._art else None
                    if pos is not None and self._idx_lift is not None:
                        cur = float(pos[0, self._idx_lift] if pos.ndim == 2
                                    else pos[self._idx_lift])
                        _set_lift_upper(cur + 0.002)
                except Exception as exc:
                    carb.log_warn("[SCENARIO] pressure_fault: " + str(exc))
            else:
                _set_lift_upper(self._nominal_lift_upper)
            self._thermal_beta = nom_beta
            _set_drive_damping(nom_damp)
            _ensure_payload(False)

        elif active == "wheel_slip":
            slip_damp = max(0.0, nom_damp - nom_damp * 0.7 * ramp_frac)
            _set_drive_damping(slip_damp)
            try:
                for rname in ("front_left_roller","front_right_roller",
                              "back_left_roller","back_right_roller"):
                    rpath = FORKLIFT_ROOT + "/roller_joints/" + rname
                    rprim = stage.GetPrimAtPath(rpath)
                    if rprim and rprim.IsValid():
                        dr = UsdPhysics.DriveAPI.Get(rprim, "angular")
                        if dr:
                            nd = dr.GetDampingAttr().Get() or 100.0
                            dr.GetDampingAttr().Set(max(1.0, nd * (1.0 - 0.9 * ramp_frac)))
            except Exception as exc:
                carb.log_warn("[SCENARIO] roller damping: " + str(exc))
            self._thermal_beta = nom_beta
            _ensure_payload(False)
            _set_lift_upper(self._nominal_lift_upper)

        else:
            # nominal — her şeyi restore et; aktif soğuma ile temp hızla düşer
            # Overheat window'dan çıkan sıcaklık nom_beta ile çok yavaş iner
            # (tau=5s), nominal label'ı kirletiyor. 5× beta → tau≈1s → 3s'de soğur.
            fast_cool = self._temperature > (THERMAL_T_AMB + 2.0)
            self._thermal_beta = nom_beta * (5.0 if fast_cool else 1.0)
            _set_drive_damping(nom_damp)
            _ensure_payload(False)
            _set_lift_upper(self._nominal_lift_upper)

    def destroy(self):
        self._on_stop()
        self._app_sub = None


# Double-init koruması: script iki kez çalıştırılırsa eski logger temizlenir
try:
    logger.destroy()
    carb.log_warn("[DTX] Eski logger temizlendi.")
except (NameError, AttributeError):
    pass

logger = DTXSensorLogger()
