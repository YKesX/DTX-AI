import omni.usd
import omni.kit.commands
import omni.kit.app
from pxr import Gf, UsdShade
import asyncio
import urllib.request
import json
import datetime

print("temiz")
stage = omni.usd.get_context().get_stage()
DANGER_CENTER = Gf.Vec3d(0, -8, 0.06)
DANGER_RADIUS = 2.5
FORKLIFT_PARTS_ALERT = [
    "/World/Forklift/Body",
    "/World/Forklift/Cabin",
    "/World/Forklift/Mast",
]
is_alert = False

def set_color(prim_path, color, emissive=(0, 0, 0)):
    shader_prim = stage.GetPrimAtPath(prim_path + "_mat/Shader")
    if not shader_prim:
        return
    shader = UsdShade.Shader(shader_prim)
    diffuse = shader.GetInput("diffuseColor")
    emissive_input = shader.GetInput("emissiveColor")
    if diffuse:
        diffuse.Set(Gf.Vec3f(*color))
    if emissive_input:
        emissive_input.Set(Gf.Vec3f(*emissive))

def get_pos(prim_path):
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        return None
    attr = prim.GetAttribute("xformOp:translate")
    if not attr:
        return None
    return attr.Get()

def send_alert_to_api(dist):
    dist_val = abs(round(float(dist), 3))  # >= 0 garantisi
    event = {
        "asset_id": "forklift_01",
        "zone_id": "danger_zone_room1",
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "vibration": dist_val,
        "metadata": {"alert_type": "proximity", "source": "isaac_sim"}
    }
    data = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:8000/events/",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read().decode("utf-8")
            print("API OK:", resp.status, body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print("API hatasi:", e.code, body)  # 500'ün tam sebebi artık görünür
    except Exception as e:
        print("Baglanti hatasi:", e)

async def proximity_check():
    global is_alert
    print("Alert sistemi basladi!")
    while True:
        pos = get_pos("/World/Forklift/Body")
        if pos:
            dist = (Gf.Vec3d(pos[0], pos[1], pos[2]) - DANGER_CENTER).GetLength()
            if dist < DANGER_RADIUS and not is_alert:
                is_alert = True
                for part in FORKLIFT_PARTS_ALERT:
                    set_color(part, (0.95, 0.05, 0.05), (0.8, 0.0, 0.0))
                print("ALERT! Forklift danger zone'da! Mesafe:", round(dist, 2))
                send_alert_to_api(dist)
            elif dist >= DANGER_RADIUS and is_alert:
                is_alert = False
                for part in FORKLIFT_PARTS_ALERT:
                    set_color(part, (0.9, 0.6, 0.05))
                print("Forklift guvende.")
        await omni.kit.app.get_app().next_update_async()

asyncio.ensure_future(proximity_check())
print("Alert sistemi aktif!")
