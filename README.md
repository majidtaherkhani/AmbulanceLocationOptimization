# Air Ambulance Location & Relocation (Pyomo)

This small **Pyomo + Gurobi** model plans where to station and when to relocate air ambulances, built with the Ontario/Ornge context in mind, but applicable anywhere.
It tries to **cover as many calls as possible** while **keeping travel for relocations low**.

- **Aircraft types:**  
  - **RW** = rotor-wing (helicopters)  
  - **FW** = fixed-wing (planes)

- **Call types:**  
  - **On-scene** → **RW only**  
  - **Interfacility** → **RW or FW**

- **How coverage is decided:**  
  - A base “covers” a demand point if it’s within a chosen distance (`coverage_threshold`).  
  - Aircraft might be busy. We use simple busy chances: `q1` for RW and `q2` for FW. More aircraft near a demand point means a higher chance at least one is free.

- **What the model chooses:**  
  - How many RW and FW sit at each base after possible moves.  
  - How many RW/FW to move from one base to another (relocations).  
  - For each demand point, a simple pick of how many RW (`a`) and FW (`b`) are effectively in range (`y[j,a,b]`).

- **What the model tries to optimize:**  
  - **Score = coverage benefit − relocation cost**  
  - Coverage benefit grows when more calls can be reached by free aircraft.  
  - Relocation cost grows with how far/ how much we move aircraft (scaled by `relocation_cost_weight`).

In short: **place and move helicopters/planes to cover more calls, without moving them around too much.**

---

## Quick Start

### Install
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install pyomo pandas folium geopy matplotlib gurobipy
