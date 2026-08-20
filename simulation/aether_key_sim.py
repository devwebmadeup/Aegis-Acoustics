import numpy as np
import matplotlib.pyplot as plt
import time

# --- 시스템 설정 값 (System Configurations) ---
GRID_SIZE = 8              # 8x8 센서 배열
NOISE_THRESHOLD = 15.0     # 무시할 주변 소음(노이즈) 임계값
PRESS_THRESHOLD = 200.0    # 햅틱을 트리거할 Z축 총 질량(누적 왜곡 강도) 임계값
DEBOUNCE_DELAY = 0.05      # 햅틱 디바운싱 지연 시간 (50ms)

# 디바운싱을 위한 전역 변수
last_haptic_time = 0

# --- 1. 가상 터치 데이터 생성 (Digital Twin Sensor) ---
def generate_virtual_touch(target_x, target_y, max_intensity=180, sigma=1.2):
    grid = np.zeros((GRID_SIZE, GRID_SIZE))
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            dist_sq = (x - target_x)**2 + (y - target_y)**2
            grid[y, x] = max_intensity * np.exp(-dist_sq / (2 * sigma**2))
    
    noise = np.random.normal(5, 3, (GRID_SIZE, GRID_SIZE))
    grid = np.clip(grid + noise, 0, 255)
    return grid

# --- 2. 핵심 로직: 무게중심(Centroid) 추적 알고리즘 ---
def calculate_centroid(sensor_data):
    total_mass = 0.0
    sum_x = 0.0
    sum_y = 0.0
    
    for x in range(GRID_SIZE):
        for y in range(GRID_SIZE):
            intensity = sensor_data[y, x]
            if intensity > NOISE_THRESHOLD:
                total_mass += intensity
                sum_x += (x * intensity)
                sum_y += (y * intensity)
                
    if total_mass == 0:
        return None, None, 0
        
    cx = sum_x / total_mass
    cy = sum_y / total_mass
    
    return cx, cy, total_mass

# --- 3. 인터랙티브 시각화 (Matplotlib UI) ---
fig, ax = plt.subplots(figsize=(7, 7))
fig.canvas.manager.set_window_title('Aether-Key PoC Simulator')

initial_grid = np.zeros((GRID_SIZE, GRID_SIZE))
heatmap = ax.imshow(initial_grid, cmap='magma', vmin=0, vmax=200, origin='upper')

crosshair, = ax.plot([], [], 'cw', markersize=15, markeredgewidth=2, label='Centroid (Sub-pixel)')
ax.legend(loc='upper right')

ax.set_xticks(np.arange(-0.5, GRID_SIZE, 1), minor=True)
ax.set_yticks(np.arange(-0.5, GRID_SIZE, 1), minor=True)
ax.grid(which='minor', color='w', linestyle='-', linewidth=1, alpha=0.2)
ax.set_title("Click to simulate mid-air touch (Distortion Blob)")

def on_click(event):
    global last_haptic_time
    if event.inaxes != ax: return
    tx, ty = event.xdata, event.ydata
    sensor_data = generate_virtual_touch(tx, ty)
    cx, cy, z_mass = calculate_centroid(sensor_data)
    
    heatmap.set_data(sensor_data)
    if cx is not None:
        crosshair.set_data([cx], [cy])
    fig.canvas.draw_idle()
    
    current_time = time.time()
    print(f"[{time.strftime('%H:%M:%S')}] 센서 데이터 계산 완료 -> Mass: {z_mass:.1f}, Coord: (X:{cx:.2f}, Y:{cy:.2f})")
    
    if z_mass > PRESS_THRESHOLD:
        if (current_time - last_haptic_time) > DEBOUNCE_DELAY:
            print(f"   ⚡ [HAPTIC FIRED] 좌표 (X:{cx:.2f}, Y:{cy:.2f})에 햅틱 펄스 발사 완료!")
            last_haptic_time = current_time
        else:
            print(f"   ⏳ [DEBOUNCED] 연속 터치 무시됨 (인지 마스킹 중)")

fig.canvas.mpl_connect('button_press_event', on_click)
plt.show()
