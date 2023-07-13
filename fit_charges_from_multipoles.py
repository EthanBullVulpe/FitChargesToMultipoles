import json
import math
import sys
import ast
import itertools
from typing import Any, MutableSequence, Sequence, Tuple
import numpy
import scipy.optimize as optimize
from scipy.optimize import LinearConstraint
import random
import sympy

global XYZ    # List of lists with coordinates of the training set elements
global N      # Max multipole to fit
global REFMP  # List of lists with the reference multipoles

def kronecker_delta(i: int, j: int) -> int:
    if i == j:
        return 1
    return 0

def lfuncp(l_min: int, l_max: int) -> int:
    if l_min <= l_max:
        return (l_max + 1)**2 - l_min**2
    else:
        return 0
    
def lfuncc(l_min: int, l_max: int) -> int:
    if l_min <= l_max:
        return ((l_max + 1)*(l_max + 2)*(l_max + 3) - l_min*(l_min+1)*(l_min+2)) // 6
    else:
        return 0
    
def konk2l(k: int) -> Tuple[int, int, int]:
    for l in range(0, 10001):
        num: int = (l+1)*(l+2)*(l+3)//6 + 1
        if k < num:
            knt: int = l*(l+1)*(l+2)//6
            
            for lz in range(0, l+1):
                for ly in range(0, l-lz+1):
                    lx = l - ly - lz
                    knt = knt + 1
                    if k == knt:
                        return (lx, ly, lz)
    raise ValueError("Could not convert k -> (lx, ly, lz)")
    
def ctopsh(l: int, m: int, lx: int, ly: int, lz: int) -> float:
    if abs(m) > l:
        raise ValueError("abs(m) > l")
    if l < 0:
        raise ValueError("l < 0")
    
    if (lx+ly-abs(m)) >= 0 and ((lx+ly-abs(m)) % 2) == 0:
        j: int = (lx+ly-abs(m)) // 2
        
        ilimit: int
        if (l-abs(m)) % 2 == 0:
            ilimit = (l-abs(m)) // 2
        else:
            ilimit = (l-abs(m)-1) // 2
            
        c1 = math.factorial(abs(m)) / (2**l*(math.prod(range(l-abs(m)+1, l+abs(m)+1))) ** (1/2))
            
        c2: int = 0
        r = range(0, ilimit+1) if ilimit >= 0 else range(ilimit, 1)
        for i in r:
            if (l-i) >= 0 and (i-j) >= 0 and (l-abs(m)-2*i) >= 0:
                c2 += (math.prod(range(l-i+1, 2*l-2*i+1))*(-1) ** i) / (math.factorial(i-j) * math.factorial(l-abs(m)-2*i))
                
        c3: int = 0    
        for k in range(0, j+1):
            if (abs(m)-lx+2*k >= 0) and (lx-2*k) >= 0:
                c3 += ((-1) ** k) / (math.factorial(k) * math.factorial(j-k) * math.factorial(lx-2*k) * math.factorial(abs(m)-lx+2*k))
        
    
        cimg: int = 0
        creal: int = 0
        if (m-lx) % 2 == 0:
            # print(f"{c1} {c2} {c3}")
            creal = c1*c2*c3*((-1)**((m-lx) / 2))
        else:
            if (m-lx+1) % 4 == 0:
                if m-lx < 0:
                    cimg = c1*c2*c3
                elif m-lx > 0:
                    cimg = -c1*c2*c3
            else:
                if m-lx < 0:
                    cimg = -c1*c2*c3
                elif m-lx > 0:
                    cimg = c1*c2*c3
                 
        c: float   
        if m == 0:
            c = creal
        elif m < 0:
            c = cimg*2**(1/2)
        else:
            c = creal*2**(1/2)
            
        return c
    
    else:
        return 0

def get_spherical_harmonics_multipoles(charges: Sequence[float], configuration: Sequence[Tuple[float, float, float]], max_multipole_level: int) -> Sequence[Sequence[float]]:
    
    multipole_moments: MutableSequence[MutableSequence[float]] = [[0.0 for m in range(-l, l+1)] for l in range(0, max_multipole_level + 1)]
    
    offset: int = 0
    
    l: int
    for l in range(0, max_multipole_level + 1):
    # for l in range(maximum_multipole_order, maximum_multipole_order + 1):
        
        # print(f"Angular Momentum QN (l): {l}\n")
        
        # l_multipole_moments: 
        
        m: int
        for m in range(-l, l+1):
            
            # print(f"Magnetic QN (m): {m}")
            
            # i is just used in the calculation of n
            i: int = lfuncp(0, l-1)
            # n is the index in the overall multipole moment array.
            multipole_index: int
            if m <= 0:
                multipole_index = i+1-2*m
            else:
                multipole_index = i+2*m
            
            # print(f"i: {i}")
            # print(f"n: {n}")
            
            for k in range(lfuncc(0, l-1)+1, lfuncc(0, l) + 1):
                # print(f"k: {k}")
                # This 'k' value might not be meaningful, and is just a key for konk2l?
                lx, ly, lz = konk2l(k)
                # print(f"(lx, ly, lz): ({lx}, {ly}, {lz})")
                coeff = ctopsh(l, m, lx, ly, lz)
                # print(f"coeff: {coeff}")
                for j in range(0, len(charges)):
                    multipole_moments[l][multipole_index-offset-1] += coeff*charges[j] * (configuration[j][0]**lx) * (configuration[j][1]**ly) * (configuration[j][2]**lz)
            
                # if lz == 2:
                #     for j in range(0, len(coords)):
                #         multipole_moments[n-1] -= coeff*(1/3)*charges[j] * (coords[j][0]**2 + coords[j][1]**2 + coords[j][2]**2)


            # multipole_moments[l][n-offset-1] *= 4.803 # not sure why need 0.5 factor
            # multipole_moments[n-1] *= 4.803 # not sure why need 0.5 factor
        offset += 2*l+1
    return multipole_moments

def get_multipoles(chg: Sequence[float], xyz: Sequence[float], n: int) -> Sequence[Sequence[float]]:
    """
    Calculates the traceless multipoles for charges in chg with positions xyz
    
    Applies formula like that for the quadrupoles here:
    https://en.wikipedia.org/wiki/Quadrupole
    
    Inputs:
    - chg          list of floats with the magnitude of the charges (size N)
    - xyz          list of floats with the coordinates of each charge (size 3N)
    - n            Maximum multipole to calculate. 0: charges, 1: dipoles, 2: quadrupoles...
    Output:
    - List of multipoles (traceless independent components)
    """

    # Check for valid max multipole
    if n < 1:
        print("Multipole order must be at least 1")
        sys.exit()

    if n > 4:
        print("Multipole orders larger than 4 not supported")
        sys.exit()

    # Charge
    multipoles = []
    multipoles.append([sum(chg)])
    
    # Dipole
    # p_i,a = qi*xa ; p_a = sum _i (q_i x_a)
    dip = [0.0]*3
    for ic,c in enumerate(chg):
        for j in range(3):
            dip[j] += c*xyz[3*ic+j]

    multipoles.append(dip)

    # Quadrupole, traceless form
    if n > 1:
        l = 2
        mpidx = sorted([ sorted(list(k)) for k in itertools.combinations_with_replacement(range(3),l)])
        this_mp = []
        # Loop over the different terms of multipole
        for term in mpidx:
            this_mp.append(0.0)
            for ic,c in enumerate(chg):
                rx = xyz[3*ic]
                ry = xyz[3*ic+1]
                rz = xyz[3*ic+2]
                r2 = rx*rx + ry*ry + rz*rz
                p = c
                for j in term:
                    p *= xyz[3*ic + j]
                this_mp[-1] += 3*p - c*r2*kronecker_delta(term[0],term[1])
        # Append multipole
        multipoles.append(this_mp)

    if n > 2:
        # Octopole, traceless form
        l = 3
        mpidx = sorted([ sorted(list(k)) for k in itertools.combinations_with_replacement(range(3),l)])
        this_mp = []
        # Loop over the different terms of multipole
        for term in mpidx:
            this_mp.append(0.0)
            for ic,c in enumerate(chg):
                rx = xyz[3*ic]
                ry = xyz[3*ic+1]
                rz = xyz[3*ic+2]
                rv = [rx,ry,rz]
                r2 = rx*rx + ry*ry + rz*rz
                p = c
                for j in term:
                    p *= xyz[3*ic + j]
                this_mp[-1] += 15*p - 3*c*r2*( rv[term[0]] * kronecker_delta(term[1],term[2])  + rv[term[1]] * kronecker_delta(term[0],term[2]) + rv[term[2]] * kronecker_delta(term[0],term[1]) ) 
        # Append multipole
        multipoles.append(this_mp)
    

    if n > 3:
        # Hexadecapole, traceless form
        l = 4
        mpidx = sorted([ sorted(list(k)) for k in itertools.combinations_with_replacement(range(3),l)])
        this_mp = []
        # Loop over the different terms of multipole
        for term in mpidx:
            this_mp.append(0.0)
            for ic,c in enumerate(chg):
                rx = xyz[3*ic]
                ry = xyz[3*ic+1]
                rz = xyz[3*ic+2]
                rv = [rx,ry,rz]
                r2 = rx*rx + ry*ry + rz*rz
                p = c
                for j in term:
                    p *= xyz[3*ic + j]
                this_mp[-1] += 105*p - 15*c*r2*( rv[term[0]] * rv[term[1]] * kronecker_delta(term[2],term[3]) + rv[term[0]] * rv[term[2]] * kronecker_delta(term[1],term[3]) + rv[term[0]] * rv[term[3]] * kronecker_delta(term[1],term[2]) + rv[term[1]] * rv[term[2]] * kronecker_delta(term[0],term[3]) + rv[term[1]] * rv[term[3]] * kronecker_delta(term[0],term[2]) + rv[term[2]] * rv[term[3]] * kronecker_delta(term[0],term[1]) ) + 3*c*r2*r2*( kronecker_delta(term[0],term[1])*kronecker_delta(term[2],term[3]) + kronecker_delta(term[0],term[2])*kronecker_delta(term[1],term[3]) + kronecker_delta(term[0],term[3])*kronecker_delta(term[1],term[2]) )

        # Append multipole
        multipoles.append(this_mp)

    ## Create the multipoles in the same format as QM codes
    multipoles_qm = []
    
    # Monopole is the same
    multipoles_qm.append(multipoles[0])
    
    # Dipole is reordered (x,y,z -> z,x,y)
    multipoles_qm.append([multipoles[1][2],multipoles[1][0],multipoles[1][1]])    

    
    if n > 1:
        # Quadrupole combines 1 term
        # Reorder: xx,xy,xz,yy,yz,zz -> zz,xz,yz,xx-yy,xy
        multipoles_qm.append([multipoles[2][5],multipoles[2][2],multipoles[2][4],multipoles[2][0]-multipoles[2][3],multipoles[2][1]])

    if n > 2:
        # Octopole
        # Reorder xxx,xxy,xxz,xyy,xyz,xzz,yyy,yyz,yzz,zzz
        # to zzz,xzz,yzz,xxz-yyz,xyz,xxx-xyy,xxy-yyy
        multipoles_qm.append([multipoles[3][9],multipoles[3][5],multipoles[3][8],multipoles[3][2]-multipoles[3][7],multipoles[3][4],multipoles[3][0]-multipoles[3][3],multipoles[3][1]-multipoles[3][6]])

    if n > 3:
        # Hexadecapole (God forgives us all....)
        # Reorder xxxx,xxxy,xxxz,xxyy,xxyz,xxzz,xyyy,xyyz,xyzz,xzzz,yyyy,yyyz,yyzz,yzzz,zzzz
        #          0    1    2    3    4    5    6    7    8    9    10   11   12   13   14 
        # to zzzz,xzzz,yzzz,xxzz-yyzz,xyzz,xxxz-xyyz,xxyz-yyyz,xxxx-xxyy+yyyy,xxxy-xyyy
        multipoles_qm.append([multipoles[4][14],multipoles[4][9],multipoles[4][13],multipoles[4][5]-multipoles[4][12],multipoles[4][8],multipoles[4][2]-multipoles[4][7],multipoles[4][4]-multipoles[4][11],multipoles[4][0]-multipoles[4][3]+multipoles[4][10],multipoles[4][1]-multipoles[4][6]])

    return multipoles_qm
      
def penalty_function(charges: Sequence[float], training_set: Sequence[Sequence[Tuple[float, float, float]]], reference_multipoles: Sequence[Sequence[Sequence[float]]], max_multipole_level: int) -> float:
    """
    Calculates the difference between calculated multipoles and reference multipoles
    Output:
    - Sum of squared residuals
    """
    # For each configuration in the ts, calculate the error
    residual: float = 0.0
    # Weights are gonna be based on the multipole
    
    for n, (configuration, ref_multipoles) in enumerate(zip(training_set, reference_multipoles)):        
        # Calculates the multipoles for the given charges
        # mpcalc = get_multipoles(params,XYZ[n],N)
        mpcalc = get_spherical_harmonics_multipoles(charges, configuration, max_multipole_level)

        # print("Current Multipoles:", mpcalc)
        # print("Reference Multipoles:", ref_multipoles)

        # Get the residual as a sum of squares of the differences in each multipole
        for i in range(max_multipole_level):
            # weight = 100/(i+1)**8
            # weight = 1 if i < 2 else 0
            weight = 1
            for j in range(len(mpcalc[i])):
                residual += weight*(mpcalc[i][j] - ref_multipoles[i][j])*(mpcalc[i][j] - ref_multipoles[i][j])
                #res += weight*((mpcalc[i][j] - REFMP[n][i][j]) / REFMP[n][i][j])*((mpcalc[i][j] - REFMP[n][i][j]) / REFMP[n][i][j])

    # print("Residual:", residual)

    return residual
        
def get_linearly_dependant_constraints(constraint_matrix: Sequence[Sequence[float]], zero_tolerance: float = 1e-3) -> Sequence[int]:
    
    # Find the indices of all linearly independent rows
    # _, linearly_independent_row_indices = sympy.Matrix(constraint_matrix).T.rref(iszerofunc = lambda x: x < zero_tolerance)
    # print("Rank:", numpy.linalg.matrix_rank(constraint_matrix, tol=1e-3))
    
    linearly_dependent_row_indices: MutableSequence[int] = []
    
    for test_index in range(0, len(constraint_matrix)):
        # print(linearly_dependent_row_indices)
        test_matrix: Sequence[Sequence[float]] = [row for index, row in enumerate(constraint_matrix) if index <= test_index and index not in linearly_dependent_row_indices]
        # print(test_matrix)
        
        # print(numpy.linalg.matrix_rank(test_matrix, tol=zero_tolerance), len(test_matrix))
        
        if numpy.linalg.matrix_rank(test_matrix, tol=zero_tolerance) < len(test_matrix):
            linearly_dependent_row_indices.append(test_index)
    
    # print(linearly_independent_row_indices)
    
    # The rows that are not linearly independent must be dependent.
    # return [row_index for row_index in range(len(constraint_matrix)) if row_index not in linearly_independent_row_indices]
    return linearly_dependent_row_indices

def get_stewart_constraints(
            configuration: Sequence[Tuple[float, float, float]],
            reference_multipoles: Sequence[Sequence[float]],
            constraint_matrix: Sequence[Sequence[float]],
            constraint_minimums: Sequence[float],
            constraint_maximums: Sequence[float],
            zero_tolerance: float = 1e-5
        ) -> Tuple[Sequence[Sequence[float]], Sequence[float], Sequence[float], int, int]:
    
    l: int = 0
    
    remaining_degrees_of_freedom: int = len(configuration) - len(constraint_matrix)
    
    stewart_constraint_matrix: MutableSequence[Sequence[float]] = []
    stewart_constraint_minimums: MutableSequence[float] = []
    stewart_constraint_maximums: MutableSequence[float] = []
    
    offset: int = 0
    
    while True:
        
        print(f"{l = } {offset = }")
        print(f"num constraints: {len(constraint_matrix) + len(stewart_constraint_matrix)}")
        print(f"remaining degrees of freedom: {remaining_degrees_of_freedom}")
        
        new_constraint_matrix: MutableSequence[MutableSequence[float]] = [[0.0 for _ in configuration] for m in range(-l, l+1)]
        new_constraint_minimums: MutableSequence[float] = [0.0 for m in range(-l, l+1)]
        new_constraint_maximums: MutableSequence[float] = [0.0 for m in range(-l, l+1)]
        
        for m, reference_multipole in zip(range(-l, l+1), reference_multipoles[l]):
            i: int = lfuncp(0, l-1)
            # n is the index in the overall multipole moment array.
            multipole_index: int
            if m <= 0:
                multipole_index = i+1-2*m
            else:
                multipole_index = i+2*m
                
            # print(f"TEST: {m = }, {multipole_index = }")
            
            for k in range(lfuncc(0, l-1)+1, lfuncc(0, l) + 1):
                lx, ly, lz = konk2l(k)
                coeff = ctopsh(l, m, lx, ly, lz)
                
                # print(f"{lx =} {ly = } {lz = } {coeff = }")
                
                for j in range(0, len(configuration)):
                    new_constraint_matrix[multipole_index-offset-1][j] += coeff * (configuration[j][0]**lx) * (configuration[j][1]**ly) * (configuration[j][2]**lz)
            
            new_constraint_minimums[multipole_index-offset-1] = reference_multipoles[l][multipole_index-offset-1] - zero_tolerance
            new_constraint_maximums[multipole_index-offset-1] = reference_multipoles[l][multipole_index-offset-1] + zero_tolerance
            
        test_constraint_matrix: MutableSequence[Sequence[float]] = []
        test_constraint_matrix.extend(constraint_matrix)
        test_constraint_matrix.extend(stewart_constraint_matrix)
        test_constraint_matrix.extend(new_constraint_matrix)
        
        print(f"new candidate constraints: {new_constraint_matrix}, {new_constraint_minimums} {new_constraint_maximums}")
        
        linearly_dependent_constraint_indices = get_linearly_dependant_constraints(test_constraint_matrix)
        
        print(f"dependent constraints: {[linearly_dependent_constraint_index - len(constraint_matrix) - len(stewart_constraint_matrix) for linearly_dependent_constraint_index in linearly_dependent_constraint_indices]}")
        
        # problem: indices change as items are removed.
        for removed_items, linearly_dependent_constraint_index in enumerate(linearly_dependent_constraint_indices):
            adjusted_index: int = linearly_dependent_constraint_index - len(constraint_matrix) - len(stewart_constraint_matrix) - removed_items
            new_constraint_matrix.pop(adjusted_index)
            new_constraint_minimums.pop(adjusted_index)
            new_constraint_maximums.pop(adjusted_index)
            
        remaining_degrees_of_freedom -= len(new_constraint_matrix)
            
        if remaining_degrees_of_freedom >= 0:
        # if remaining_degrees_of_freedom > 0:
            stewart_constraint_matrix.extend(new_constraint_matrix)
            stewart_constraint_minimums.extend(new_constraint_minimums)
            stewart_constraint_maximums.extend(new_constraint_maximums)
        if remaining_degrees_of_freedom == 0:
            return stewart_constraint_matrix, stewart_constraint_minimums, stewart_constraint_maximums, l, l
        if remaining_degrees_of_freedom < 0:
        # if remaining_degrees_of_freedom <= 0:
            return stewart_constraint_matrix, stewart_constraint_minimums, stewart_constraint_maximums, l-1, l
        
        offset += 2*l+1
        l += 1

def read_training_set(training_set_path: str) -> Tuple[Sequence[Sequence[Tuple[float, float, float]]], Sequence[Sequence[Sequence[float]]]]:
    """
    Reads the training set: an xyz file with the multipoles on the comment line
    Returns the number of atoms, the coordinates and the multipoles
    """
    xyz: MutableSequence[MutableSequence[Tuple[float, float, float]]] = []
    mp: MutableSequence[MutableSequence[Sequence[float]]] = []
    with open(training_set_path,'r') as ff:
    
        line = ff.readline()
        nat = int(line.strip().split()[0])
        while line != "":
            mpi = ast.literal_eval(ff.readline().strip())
            xyzi: MutableSequence[Tuple[float, float, float]] = []
            for i in range(nat):
                toks = ff.readline().strip().split()
                xyzi.append((float(toks[1]), float(toks[2]), float(toks[3])))
            xyz.append(xyzi)
            mp.append(mpi)
            line = ff.readline()

    return xyz,mp

def fit_multipoles(
            training_set_configurations: Sequence[Sequence[Tuple[float, float, float]]],
            reference_multipoles: Sequence[Sequence[Sequence[float]]],
            starting_charges: Sequence[float],
            max_multipole_level: int,
            constraint_matrix: Sequence[Sequence[float]] = [],
            constraint_min: Sequence[float] = [],
            constraint_max: Sequence[float] = []
        ) -> Sequence[float]:
    
    def callback(charges: Sequence[float], *args: Any) -> None:
        current_penalty: float = penalty_function(charges, training_set=training_set_configurations, reference_multipoles=reference_multipoles, max_multipole_level=max_multipole_level)
        print("Current Penalty:", current_penalty)
        
    def penalty_function_wrapper(charges, arg_dict):
        return penalty_function(charges, arg_dict["training_set"], arg_dict["reference_multipoles"], arg_dict["max_multipole_level"])
        
    linear_constraint = LinearConstraint(constraint_matrix,constraint_min,constraint_max)
    
    print(constraint_matrix)
    
    result = optimize.minimize(penalty_function_wrapper, starting_charges, constraints=(linear_constraint,), tol=1e-5, callback=callback, args = {"training_set": training_set_configurations, "reference_multipoles": reference_multipoles, "max_multipole_level": max_multipole_level})

    final_charges: Sequence[float] = result.x
    
    return final_charges

# MAIN FUNCTION #

if len(sys.argv) != 2:
    print(f"Usage: python3 {sys.argv[0]} <input.json>")
    sys.exit()

json_path = sys.argv[1]

# Read JSON file
with open(json_path,'r') as json_file:
    json_data = json.load(json_file)

# Set up variables
# Initial guess
min_guess = json_data["min_guess"]
max_guess = json_data["max_guess"]

charges: Sequence[float]
if "charges" in json_data:
    charges = json_data["charges"]
else:
    charges = [min + random.random()*(max-min) for min, max in zip(min_guess, max_guess)]
print("Initial Guess:", charges)

# Training set
training_set_path = json_data['training_set']
training_set_configurations, reference_multipoles = read_training_set(training_set_path)


# Check for consistency between charges and coordinates
if len(charges) != len(training_set_configurations[0]):
    print(f"ERROR: Charges size ({len(charges)}) is not consistent with coordinate size ({len(training_set_configurations[0])})")
    sys.exit()

# Max multipole
N = json_data["n"] 

# Check consistency between reference multipoles and multipoles to calculate
# Ref multiples must be at least same length as N
if N > len(reference_multipoles[0]):
    print(f"ERROR: N ({N}) is larger than the reference number of multipoles provided ({len(reference_multipoles[0])})")
    sys.exit()

# Add constraints, if any
constraint_matrix: MutableSequence[Sequence[float]] = json_data["constraint_matrix"]
constraint_minimums: MutableSequence[float] = json_data["constraint_minimums"]
constraint_maximums: MutableSequence[float] = json_data["constraint_maximums"]

if len(get_linearly_dependant_constraints(constraint_matrix)) > 0:
    print(f"Initial constraint matrix contains linearly dependant constraints.")
    print(f"Matrix:")
    print(f"{constraint_matrix}")
    print(f"Linearly dependent constraints: {get_linearly_dependant_constraints(constraint_matrix)}")
    
stewart_constraint_matrix, stewart_constraint_minimums, stewart_constraint_maximums, stewart_constraint_level, stewart_fitting_level = get_stewart_constraints(
        training_set_configurations[0],
        reference_multipoles[0],
        constraint_matrix,
        constraint_minimums,
        constraint_maximums
)

print(f"Adding {len(stewart_constraint_matrix)} additional Stewart constraints using multipoles up to L={stewart_constraint_level}")

constraint_matrix.extend(stewart_constraint_matrix)
constraint_minimums.extend(stewart_constraint_minimums)
constraint_maximums.extend(stewart_constraint_maximums)

print(f"Will now fit multipoles up to L={stewart_fitting_level}")

print("Multipoles of initial charges")
print([[val for val in list] for list in get_spherical_harmonics_multipoles(charges, training_set_configurations[0], len(reference_multipoles[0]) - 1)])

final_charges: Sequence[float] = fit_multipoles(
        training_set_configurations,
        reference_multipoles,
        charges,
        constraint_matrix=constraint_matrix,
        constraint_min=constraint_minimums,
        constraint_max=constraint_maximums,
        max_multipole_level=stewart_fitting_level
)

# if len(constraints) != 3:
#     print("No valid constraints have been found. Running optimization without constraints")
#     result = optimize.minimize(penalty_function,charges)
# else:
#     linear_constraint = LinearConstraint(constraints[0],constraints[1],constraints[2])
#     result = optimize.minimize(penalty_function,charges,constraints=(linear_constraint,), tol=1e-8, options={"maxiter": 1000})

# Report

mp = get_spherical_harmonics_multipoles(final_charges, training_set_configurations[0],N)
print("\n\nResiduals:\n")

for i in range(len(mp)):
    print("i = {}     ".format(i), [mp[i][j] - reference_multipoles[0][i][j] for j in range(len(mp[i]))])
    
print(f"Total penalty: {penalty_function(final_charges, training_set_configurations, reference_multipoles, max_multipole_level=stewart_fitting_level)}")

print("\n\nFitted charges:\n")
print([round(float(q),4) for q in final_charges])

# print("\n\nMultipoles:\n")
# for n in range(len(XYZ)):        
#     # Calculates the multipoles for the given charges
#     mpcalc = get_spherical_harmonics_multipoles(result.x,XYZ[n],N)

#     print("Predicted:", mpcalc)
#     print("Reference:", REFMP[n])

print("\n\n")
