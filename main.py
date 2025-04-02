from pyomo.environ import *
from pyomo.opt import SolverFactory
import pandas as pd

class AirAmbulanceRelocationModel:
    def __init__(self, I, J, D, d_ij, d_ii, initial_x_RW, initial_x_FW, q1, q2, coverage_threshold, relocation_cost_weight):
        self.I = I
        self.J = J
        self.D = D
        self.d_ij = d_ij
        self.d_ii = d_ii
        self.initial_x_RW = initial_x_RW
        self.initial_x_FW = initial_x_FW
        self.q1 = q1
        self.q2 = q2
        self.coverage_threshold = coverage_threshold
        self.relocation_cost_weight = relocation_cost_weight

        self.cover_sets = {j: [i for i in I if d_ij.get((i, j), 999) < coverage_threshold] for j in self.J}
        
        self.A_max = sum(initial_x_RW.values())
        self.B_max = sum(initial_x_FW.values())
        self.model = None

    def build_model(self):
        
        m = ConcreteModel()
        
        m.I = Set(initialize=self.I)
        m.J = Set(initialize=self.J)
        m.A = RangeSet(0, self.A_max)
        m.B = RangeSet(0, self.B_max)
        
        m.D = Param(m.J, initialize=self.D)
        m.d_ij = Param(m.I, m.J, initialize=self.d_ij, default=999)
        m.d_ii = Param(m.I, m.I, initialize=self.d_ii, default=999)
        m.q1 = Param(initialize=self.q1)
        m.q2 = Param(initialize=self.q2)
        m.w = Param(initialize=self.relocation_cost_weight)
        m.initial_x_RW = Param(m.I, initialize=self.initial_x_RW)
        m.initial_x_FW = Param(m.I, initialize=self.initial_x_FW)
        m.coverage_threshold = Param(initialize=self.coverage_threshold)

        m.x_RW = Var(m.I, domain=NonNegativeIntegers)
        m.x_FW = Var(m.I, domain=NonNegativeIntegers)
        m.r_RW = Var(m.I, m.I, domain=NonNegativeIntegers)
        m.r_FW = Var(m.I, m.I, domain=NonNegativeIntegers)
        m.y = Var(m.J, m.A, m.B, domain=Binary)

        
        m.RWBalance = Constraint(m.I, rule=self.RW_balance_rule)
        m.FWBalance = Constraint(m.I, rule=self.FW_balance_rule)
        m.CoverageCombo = Constraint(m.J, rule=self.coverage_combo_rule)
        m.sum_RW_coverage = Expression(m.J, rule=self.sum_RW_coverage)
        m.sum_FW_coverage = Expression(m.J, rule=self.sum_FW_coverage)
        m.ValidCoverage_RW_Upper = Constraint(m.J, m.A, m.B, rule=self.valid_coverage_RW_upper)
        m.ValidCoverage_RW_Lower = Constraint(m.J, m.A, m.B, rule=self.valid_coverage_RW_lower)
        m.ValidCoverage_FW_Upper = Constraint(m.J, m.A, m.B, rule=self.valid_coverage_FW_upper)
        m.ValidCoverage_FW_Lower = Constraint(m.J, m.A, m.B, rule=self.valid_coverage_FW_lower)

        m.Obj = Objective(rule=self.obj_rule, sense=maximize)

        self.model = m

    def RW_balance_rule(self, m, i):
        return m.x_RW[i] == m.initial_x_RW[i] + sum(m.r_RW[ip, i] for ip in m.I) - sum(m.r_RW[i, ip] for ip in m.I)

    def FW_balance_rule(self, m, i):
        return m.x_FW[i] == m.initial_x_FW[i] + sum(m.r_FW[ip, i] for ip in m.I) - sum(m.r_FW[i, ip] for ip in m.I)

    def coverage_combo_rule(self, m, j):
        return sum(m.y[j, a, b] for a in m.A for b in m.B) == 1

    def sum_RW_coverage(self, m, j):
        return sum(m.x_RW[i] for i in self.cover_sets.get(j, []))

    def sum_FW_coverage(self, m, j):
        return sum(m.x_FW[i] for i in self.cover_sets.get(j, []))

    def valid_coverage_RW_upper(self, m, j, a, b):
        M = max(self.A_max, self.B_max) * len(self.I)
        return m.sum_RW_coverage[j] - a <= M * (1 - m.y[j, a, b])

    def valid_coverage_RW_lower(self, m, j, a, b):
        M = max(self.A_max, self.B_max) * len(self.I)
        return a - m.sum_RW_coverage[j] <= M * (1 - m.y[j, a, b])

    def valid_coverage_FW_upper(self, m, j, a, b):
        M = max(self.A_max, self.B_max) * len(self.I)
        return m.sum_FW_coverage[j] - b <= M * (1 - m.y[j, a, b])

    def valid_coverage_FW_lower(self, m, j, a, b):
        M = max(self.A_max, self.B_max) * len(self.I)
        return b - m.sum_FW_coverage[j] <= M * (1 - m.y[j, a, b])

    def obj_rule(self, m):
        coverage_obj = sum(
            m.D[j]['interfacility_demand'] * sum((1 - (m.q1**a) * (m.q2**b)) * m.y[j, a, b] for a in m.A for b in m.B)
            for j in m.J if self.D[j]['interfacility_demand'] > 0
        )
        coverage_obj += sum(
            m.D[j]['onscene_demand'] * sum((1 - m.q1**a) * m.y[j, a, b] for a in m.A for b in m.B)
            for j in m.J if self.D[j]['onscene_demand'] > 0
        )

        relocation_cost = sum(
            m.w * m.d_ii[i, ip] * (m.r_RW[i, ip] + m.r_FW[i, ip])
            for i in m.I for ip in m.I if i != ip
        )
        return coverage_obj - relocation_cost




demand_points_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_demand_points')
base_locations_case1_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_bases_case1')
base_locations_case2_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_bases_case2')
demands_period1_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_demands_period1')
demands_period2_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_demands_period2')
distances_base_base_case1_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_distances_bases1_bases1')
distances_base_base_case2_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_distances_bases2_bases2')
distances_base_case1_demand_point_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_distances_bases1_demand_p')
distances_base_case2_demand_point_df = pd.read_excel('C:/Users/asus/Downloads/datasettt.xlsx', sheet_name='table_distances_bases2_demand_p')


demand_points_df.head()
demand_points = {}
J = []

for _, row in demand_points_df.iterrows():
    demand_points[row['index']] = {
        'name': row['Demand areas'],
        'latitude': row['Latitude'],
        'longitude': row['Longitude'],
    }
    J.append(row['index'])

I_case1 = []
I_case2 = []
I_case2 = []
I_case1_locations = {}
I_case2_locations = {}

for _, row in base_locations_case1_df.iterrows():
    I_case1_locations[row['index']] = {
        'latitude': demand_points[row['location_index']]['latitude'],
        'longitude': demand_points[row['location_index']]['longitude']
    }
    I_case1.append(row['index'])
    
for _, row in base_locations_case2_df.iterrows():
    I_case2_locations[row['index']] = {
        'latitude': demand_points[row['location_index']]['latitude'],
        'longitude': demand_points[row['location_index']]['longitude']
    }
    I_case2.append(row['index'])



d_ii_case1 = {}
d_ii_case2 = {}
D_period1 = {}
D_period2 = {}

for i in range(1, distances_base_base_case1_df.shape[0] + 1):
    for j in range(1, distances_base_base_case1_df.shape[1]):
        d_ii_case1[(i, j)] = distances_base_base_case1_df.iloc[i-1, j]

for i in range(1, distances_base_base_case2_df.shape[0] + 1):
    for j in range(1, distances_base_base_case2_df.shape[1]):
        d_ii_case2[(i, j)] = distances_base_base_case2_df.iloc[i-1, j]


d_ij_case1 = {}
d_ij_case2 = {}

for i in range(1, distances_base_case1_demand_point_df.shape[0] + 1):
    for j in range(1, distances_base_case1_demand_point_df.shape[1]):
        d_ij_case1[(i, j)] = distances_base_case1_demand_point_df.iloc[i-1, j]

for i in range(1, distances_base_case2_demand_point_df.shape[0] + 1):
    for j in range(1, distances_base_case2_demand_point_df.shape[1]):
        d_ij_case2[(i, j)] = distances_base_case2_demand_point_df.iloc[i-1, j]

for _, row in demands_period1_df.iterrows():
    D_period1[row['location_index']] = {
        'interfacility_demand': row['interfacility_demand'],
        'onscene_demand': row['onscene_demand']
    }

for _, row in demands_period2_df.iterrows():
    D_period2[row['location_index']] = {
        'interfacility_demand': row['interfacility_demand'],
        'onscene_demand': row['onscene_demand']
    }

q1 = 0.3
q2 = 0.3
coverage_threshold = 80
relocation_cost_weight =0.001

initial_x_RW = {base: 1 for base in I_case1}
initial_x_FW = {base: 1 for base in I_case1}

initial_x_RW[1] = 0
initial_x_RW[2] = 2
initial_x_RW[3] = 0
initial_x_RW[4] = 3
initial_x_RW[5] = 0
initial_x_RW[6] = 1

initial_x_FW[1] = 0
initial_x_FW[2] = 1
initial_x_FW[3] = 3
initial_x_FW[4] = 0
initial_x_FW[5] = 1
initial_x_FW[6] = 1

model_instance = AirAmbulanceRelocationModel(I_case1, J, D_period2, d_ij_case1, d_ii_case1,
                                               initial_x_RW, initial_x_FW,
                                               q1, q2, coverage_threshold, relocation_cost_weight)
model_instance.build_model()
opt = SolverFactory('gurobi')
opt.options['MIPGap'] = 0.1
results = opt.solve(model_instance.model, tee=True)

print("\nObjective Function Value:", model_instance.model.Obj())

print("\nStationed RW Aircraft:")
for i in model_instance.model.I:
    print(f"{i}: {model_instance.model.x_RW[i].value}")

print("\nStationed FW Aircraft:")
for i in model_instance.model.I:
    print(f"{i}: {model_instance.model.x_FW[i].value}")

print("\nRelocation Flows:")

for i in model_instance.model.I:
    for ip in model_instance.model.I:
        if i != ip:
            if value(model_instance.model.r_FW[i, ip]) > 0:
                print(f"FW: {i} -> {ip}: {value(model_instance.model.r_FW[i, ip])}")
            if value(model_instance.model.r_RW[i, ip]) > 0:
                print(f"RW: {i} -> {ip}: {value(model_instance.model.r_RW[i, ip])}")
            

final_conver_set ={}
print("\nCoverage Assignments:")
for j in model_instance.model.J:
    for a in model_instance.model.A:
        for b in model_instance.model.B:
            if value(model_instance.model.y[j, a, b]) > 0:
                actual_covering_bases = [
                    i for i in model_instance.cover_sets[j]
                    if value(model_instance.model.x_RW[i]) > 0 or value(model_instance.model.x_FW[i]) > 0
                ]
                final_conver_set[j] = actual_covering_bases
                
                
import folium
from geopy.distance import geodesic

latitudes = [point['latitude'] for point in demand_points.values()]
longitudes = [point['longitude'] for point in demand_points.values()]
map_center = [sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes)]

m = folium.Map(location=map_center, zoom_start=12)


for point_id, point_data in demand_points.items():
    folium.CircleMarker(
        location=[point_data['latitude'], point_data['longitude']],
        radius=2,
        color='red',
        fill=True,
        fill_color='red',
        fill_opacity=0.5
    ).add_to(m)


for demand_index, base_locations in final_conver_set.items():
    demand_point = demand_points[demand_index]
    demand_coords = (demand_point['latitude'], demand_point['longitude'])

    for base_index in base_locations:
        base_location = I_case1_locations[base_index]
        base_coords = (base_location['latitude'], base_location['longitude'])

        folium.PolyLine(
            locations=[base_coords, demand_coords],
            color='blue',
            weight=0.6,
            opacity=0.5
        ).add_to(m)

        folium.CircleMarker(
            location=base_coords,
            radius=2,
            color='blue',
            fill=True,
            fill_color='blue',
            fill_opacity=0.5
        ).add_to(m)

m.save("map.html")

coverage_obj_value = sum(
    model_instance.model.D[j]['interfacility_demand'] * sum(((1 - model_instance.model.q1**a * (model_instance.model.q2**b)) ) * model_instance.model.y[j, a, b].value for a in model_instance.model.A for b in model_instance.model.B)
    for j in model_instance.model.J if model_instance.D[j]['interfacility_demand'] > 0
)
coverage_obj_value += sum(
    model_instance.model.D[j]['onscene_demand'] * sum((1 - model_instance.model.q1**a) * model_instance.model.y[j, a, b].value for a in model_instance.model.A for b in model_instance.model.B)
    for j in model_instance.model.J if model_instance.D[j]['onscene_demand'] > 0
)
print("\nCoverage Objective Part:", coverage_obj_value)

relocation_cost_value = sum(
    model_instance.model.w * model_instance.model.d_ii[i, ip] * (model_instance.model.r_RW[i, ip].value + model_instance.model.r_FW[i, ip].value)
    for i in model_instance.model.I for ip in model_instance.model.I if i != ip
)
print("\nRelocation Cost Objective Part:", relocation_cost_value)



import matplotlib.pyplot as plt

# Data (unchanged)
case1_period1_ob = {0.1:[717, 725], 0.03:[719, 727], 0.01:[719, 731], 0.001:[724, 735]}
case1_period1_ob_part1 = {0.1:[717], 0.03:[721], 0.01:[723], 0.001:[728]}
case1_period1_ob_part2 = {0.1:[0], 0.03:[2.13], 0.01:[4.55], 0.001:[4.05]}
case1_period1_distance = {0.1:[0], 0.03:[71], 0.01:[455], 0.001:[4050]}

case1_period2_ob = {0.1:[732, 741], 0.03:[721, 786], 0.01:[733,780], 0.001:[743, 749]}
case1_period2_ob_part1 = {0.1:[732], 0.03:[737], 0.01:[738], 0.001:[743]}
case1_period2_ob_part2 = {0.1:[0], 0.03:[16.02], 0.01:[5.55], 0.001:[0.1]}
case1_period2_distances = {0.1:[0], 0.03:[534], 0.01:[555], 0.001:[100]}


fig1, axs1 = plt.subplots(2, 2, figsize=(10, 8))

keys = sorted(case1_period1_ob.keys())
axs1[0, 0].plot(keys, [case1_period1_ob[k][0] for k in keys], 'r', label='Objective Values')
axs1[0, 0].plot(keys, [case1_period1_ob[k][1] for k in keys], 'b', label='Best Bounds')
axs1[0, 0].set_title('Objective Function')
axs1[0, 0].set_xlabel('Relocation Cost Weight')
axs1[0, 0].set_ylabel('Value')
axs1[0, 0].legend()

axs1[0, 1].plot(keys, [case1_period1_ob_part1[k][0] for k in keys], 'b')
axs1[0, 1].set_title('Coverage Component')
axs1[0, 1].set_xlabel('Relocation Cost Weight')
axs1[0, 1].set_ylabel('Value')

axs1[1, 0].plot(keys, [case1_period1_ob_part2[k][0] for k in keys], 'b')
axs1[1, 0].set_title('Relocation Cost Component')
axs1[1, 0].set_xlabel('Relocation Cost Weight')
axs1[1, 0].set_ylabel('Value')

axs1[1, 1].plot(keys, [case1_period1_distance[k][0] for k in keys], 'b')
axs1[1, 1].set_title('Relocation Distance')
axs1[1, 1].set_xlabel('Relocation Cost Weight')
axs1[1, 1].set_ylabel('Distance')

fig1.tight_layout()


fig2, axs2 = plt.subplots(2, 2, figsize=(10, 8))

keys = sorted(case1_period2_ob.keys())
axs2[0, 0].plot(keys, [case1_period2_ob[k][0] for k in keys], 'r', label='Objective Values')
axs2[0, 0].plot(keys, [case1_period2_ob[k][1] for k in keys], 'b', label='Best Bounds')
axs2[0, 0].set_title('Objective Function')
axs2[0, 0].set_xlabel('Relocation Cost Weight')
axs2[0, 0].set_ylabel('Value')
axs2[0, 0].legend()

axs2[0, 1].plot(keys, [case1_period2_ob_part1[k][0] for k in keys], 'b')
axs2[0, 1].set_title('Coverage Component')
axs2[0, 1].set_xlabel('Relocation Cost Weight')
axs2[0, 1].set_ylabel('Value')

axs2[1, 0].plot(keys, [case1_period2_ob_part2[k][0] for k in keys], 'b')
axs2[1, 0].set_title('Relocation Cost Component')
axs2[1, 0].set_xlabel('Relocation Cost Weight')
axs2[1, 0].set_ylabel('Value')

axs2[1, 1].plot(keys, [case1_period2_distances[k][0] for k in keys], 'b')
axs2[1, 1].set_title('Relocation Distance')
axs2[1, 1].set_xlabel('Relocation Cost Weight')
axs2[1, 1].set_ylabel('Distance')

fig2.tight_layout()

plt.show()
