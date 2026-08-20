"""Concept-only animation of an idealized shield boundary.

This file intentionally does *not* model an acoustic pressure field, aerosol
drag, diffusion, or deposition.  It is useful for explaining the intended
interaction, but it must not be cited as physical feasibility evidence.  Use
``aegis_radiation_force_feasibility.py`` for the bounded analytical check.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

# --- 1. 시스템 및 물리 환경 설정 ---
WIDTH, HEIGHT = 100, 100
NUM_PARTICLES = 50
SHIELD_CENTER = (50, 20)
SHIELD_RADIUS = 25
GRAVITY = 0.5       # arbitrary animation distance / frame^2
SHIELD_FORCE = 3.0  # arbitrary animation velocity; not a force in newtons

# 입자 초기화 (무작위 위치에서 떨어지도록)
particles = np.zeros((NUM_PARTICLES, 4)) # [x, y, vx, vy]
particles[:, 0] = np.random.uniform(10, 90, NUM_PARTICLES)
particles[:, 1] = np.random.uniform(80, 100, NUM_PARTICLES)
particles[:, 3] = -np.random.uniform(0.5, 2.0, NUM_PARTICLES) # 초기 하강 속도

shield_active = True

# --- 2. 시각화 (Matplotlib) 설정 ---
fig, ax = plt.subplots(figsize=(6, 6))
fig.canvas.manager.set_window_title('Aegis Acoustic Shield Physics Simulation')
ax.set_xlim(0, WIDTH)
ax.set_ylim(0, HEIGHT)
ax.set_aspect('equal')
ax.set_facecolor('#0f172a') # 다크 테마 배경

# 반도체 웨이퍼 (바닥) 표시
wafer = plt.Rectangle((20, 0), 60, 5, color='#475569')
ax.add_patch(wafer)

# 입자 산점도 표시
scatter = ax.scatter(particles[:, 0], particles[:, 1], c='#facc15', s=10)

# 방어막(Shield) 가시화 - 활성화 시 청록색 돔 표시
theta = np.linspace(0, np.pi, 100)
shield_x = SHIELD_CENTER[0] + SHIELD_RADIUS * np.cos(theta)
shield_y = SHIELD_CENTER[1] + SHIELD_RADIUS * np.sin(theta)
shield_line, = ax.plot(shield_x, shield_y, c='#2dd4bf', lw=2, alpha=0.8, ls='--')

ax.set_title("Aegis Shield: ON (Click to Toggle)", color='white')

# --- 3. 물리 엔진 업데이트 루프 ---
def update(frame):
    global particles, shield_active

    for i in range(NUM_PARTICLES):
        # 1. 중력 적용
        particles[i, 3] -= GRAVITY * 0.1

        # 2. 위치 업데이트
        particles[i, 0] += particles[i, 2]
        particles[i, 1] += particles[i, 3]

        # 3. 개념적 방어막 충돌 계산 (정량 acoustic-force 모델이 아님)
        if shield_active:
            dx = particles[i, 0] - SHIELD_CENTER[0]
            dy = particles[i, 1] - SHIELD_CENTER[1]
            dist = np.sqrt(dx**2 + dy**2)

            # 입자가 방어막 반경 안에 들어왔을 때 (돔 위쪽)
            if 0 < dist < SHIELD_RADIUS and dy > 0:
                # 임의 단위의 튕김 속도 벡터 계산
                kick_x = (dx / dist) * SHIELD_FORCE
                kick_y = (dy / dist) * SHIELD_FORCE

                # 속도 반전 및 가속 (탄성 충돌 + 방사압)
                particles[i, 2] = kick_x
                particles[i, 3] = np.abs(particles[i, 3]) * 0.5 + kick_y

        # 4. 바닥(웨이퍼) 충돌 또는 화면 밖 이탈 시 입자 재생성
        if (
            particles[i, 1] < 0
            or particles[i, 1] > HEIGHT
            or particles[i, 0] < 0
            or particles[i, 0] > WIDTH
        ):
            particles[i, 0] = np.random.uniform(10, 90)
            particles[i, 1] = np.random.uniform(80, HEIGHT)
            particles[i, 2] = 0
            particles[i, 3] = -np.random.uniform(0.5, 2.0)

    scatter.set_offsets(particles[:, :2])
    return scatter,

# --- 4. 마우스 클릭 토글 이벤트 ---
def on_click(event):
    global shield_active
    shield_active = not shield_active

    if shield_active:
        shield_line.set_alpha(0.8)
        ax.set_title("Aegis Shield: ON (Click to Toggle)", color='white')
    else:
        shield_line.set_alpha(0.0) # 방어막 끄기
        ax.set_title("Aegis Shield: OFF (Particles Contaminating)", color='#ef4444')

fig.canvas.mpl_connect('button_press_event', on_click)

if __name__ == '__main__':
    ani = animation.FuncAnimation(fig, update, frames=200, interval=20, blit=True)
    plt.show()
