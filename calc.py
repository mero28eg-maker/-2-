from datetime import date
from typing import List, Tuple
import math, time

# constants
STEP_UNITS = 10   # 0.1 m³
TOL_MILLS  = 1    # 0.001 EGP
STAMP_DEFAULT = 0.036
TIME_BUDGET = 0.12

def tiers_from_p1(p1: float) -> Tuple[float, float]:
    p1r = round(p1, 2)
    if p1r == 2.35: return 3.1, 3.6
    if p1r == 2.50: return 3.25, 3.75
    if p1r == 2.60: return 3.35, 4.0
    if p1r == 3.00: return 4.0, 5.0
    if p1r == 4.00: return 5.0, 7.0
    p2 = p1 + 0.75; p3 = p2 + 0.5
    return p2, p3

def price_mills(q: float, p1: float, p2: float, p3: float, fee: float, stamp: float) -> int:
    t1, t2, t3 = p1 + stamp, p2 + stamp, p3 + stamp
    if q <= 30.0:
        v = q * t1
    elif q <= 60.0:
        v = 30.0 * t1 + (q - 30.0) * t2
    else:
        v = 30.0 * t1 + 30.0 * t2 + (q - 60.0) * t3
    v += fee
    return int(round(v * 1000.0))

def price_no_fee(q: float, p1: float, p2: float, p3: float, stamp: float) -> float:
    t1, t2, t3 = p1 + stamp, p2 + stamp, p3 + stamp
    if q <= 30.0:
        v = q * t1
    elif q <= 60.0:
        v = 30.0 * t1 + (q - 30.0) * t2
    else:
        v = 30.0 * t1 + 30.0 * t2 + (q - 60.0) * t3
    return round(v, 3)

def build_price_table(umax: int, p1: float, p2: float, p3: float, fee: float, stamp: float):
    tbl = [0]*(umax+1)
    for u in range(umax+1):
        tbl[u] = price_mills(u/STEP_UNITS, p1, p2, p3, fee, stamp)
    return tbl

def month_range_inclusive(start_d: date, end_d: date):
    s = date(start_d.year, start_d.month, 1)
    e = date(end_d.year, end_d.month, 1)
    out = []
    cur = s
    while cur <= e and len(out) < 12:
        out.append(cur)
        y, m = cur.year, cur.month
        cur = date(y+1, 1, 1) if m == 12 else date(y, m+1, 1)
    if not out: out = [s]
    return out

def optimize_distribution(months: int,
                          target_q: float,
                          target_v: float,
                          p1: float, p2: float, p3: float,
                          fee: float, stamp: float,
                          fixed_quantities: List[float],
                          first_month_min_q: float = 0.0,
                          last_month_fixed_q: float = 0.0):
    totalU = int(round(max(0.0, target_q) * STEP_UNITS))
    umax = max(totalU, 1200)
    price_tbl = build_price_table(umax, p1, p2, p3, fee, stamp)

    minU = [0]*months
    maxU = [umax]*months
    qU   = [0]*months
    vM   = [0]*months

    # apply fixed quantities (including zeros)
    for i in range(months):
        fx = fixed_quantities[i]
        if fx is not None:
            u = int(round(max(0.0, fx) * STEP_UNITS))
            minU[i] = u; maxU[i] = u; qU[i] = u

    # first month minimum
    if months >= 1 and fixed_quantities[0] is None:
        minU[0] = max(minU[0], int(round(max(0.0, first_month_min_q) * STEP_UNITS)))

    # last month fixed to c3 if not already fixed by user
    if months >= 1 and last_month_fixed_q > 0.0 and fixed_quantities[months-1] is None:
        u = int(round(last_month_fixed_q * STEP_UNITS))
        minU[months-1] = u; maxU[months-1] = u; qU[months-1] = u

    # deterministic start: fill min, then spread remaining by caps
    sumMin = sum(minU)
    left = max(0, totalU - sumMin)
    caps = [max(0, maxU[i] - minU[i]) for i in range(months)]
    qU = minU[:]

    if left > 0 and sum(caps) > 0:
        # proportional add
        add = [0]*months
        need = 0
        for i in range(months):
            if caps[i] > 0:
                frac = left * (caps[i]/sum(caps))
                a = int(math.floor(frac))
                a = min(a, caps[i])
                add[i] = a; need += a
        rem = left - need
        for i in range(months):
            if rem <= 0: break
            if caps[i] - add[i] > 0:
                add[i] += 1; rem -= 1
        for i in range(months):
            qU[i] += add[i]

    for i in range(months): vM[i] = price_tbl[qU[i]]
    targetM = int(round(max(0.0, target_v) * 1000.0))

    bestQ = qU[:]; bestV = vM[:]; bestDiff = abs(sum(vM) - targetM)

    t0 = time.time()
    while time.time() - t0 <= TIME_BUDGET:
        cur = sum(vM)
        if abs(cur - targetM) <= TOL_MILLS:
            bestQ = qU[:]; bestV = vM[:]; bestDiff = 0; break

        needUp = cur < targetM
        gain = [-(10**12)]*months
        loss = [10**12]*months

        for i in range(months):
            if qU[i] < maxU[i]:
                gain[i] = price_tbl[qU[i]+1] - vM[i]
            if qU[i] > minU[i]:
                loss[i] = vM[i] - price_tbl[qU[i]-1]

        if needUp:
            iBest = max(range(months), key=lambda k: gain[k])
            jBest = min(range(months), key=lambda k: loss[k])
            if gain[iBest] <= -(10**11) or loss[jBest] >= 10**11: break
            qU[iBest] += 1; vM[iBest] = price_tbl[qU[iBest]]
            qU[jBest] -= 1; vM[jBest] = price_tbl[qU[jBest]]
        else:
            iBest = min(range(months), key=lambda k: gain[k])
            jBest = max(range(months), key=lambda k: loss[k])
            if gain[iBest] <= -(10**11) or loss[jBest] >= 10**11: break
            qU[iBest] += 1; vM[iBest] = price_tbl[qU[iBest]]
            qU[jBest] -= 1; vM[jBest] = price_tbl[qU[jBest]]

        cur = sum(vM)
        d = abs(cur - targetM)
        if d < bestDiff:
            bestDiff = d; bestQ = qU[:]; bestV = vM[:]
        if bestDiff <= TOL_MILLS: break

    q = [u/STEP_UNITS for u in bestQ]
    v = [vm/1000.0 for vm in bestV]
    return q, v

def compute_headers_and_distribution(
    b2, c2, d2, e2, sdate,
    b3, c3, d3, e3, edate,
    topup1=0.0, topup2=0.0,
    p1=2.5, fee=0.0, stamp=STAMP_DEFAULT,
    fixed_quantities=None
):
    p2, p3 = tiers_from_p1(p1)

    # F6
    f6 = round((e2 or 0.0) + (topup1 or 0.0) + (topup2 or 0.0), 3)
    # F10/F11 (no fee)
    f10 = price_no_fee(d2 or 0.0, p1, p2, p3, stamp)
    f11 = price_no_fee(d3 or 0.0, p1, p2, p3, stamp)
    # F8
    f8 = (b3 or 0.0) - (d3 or 0.0) - (b2 or 0.0) + (d2 or 0.0)
    if f8 < 0: f8 = 0.0
    f8 = round(f8, 1)
    # F9
    f9 = (f6 + f10) - ((e3 or 0.0) + f11)
    f9 = round(f9, 3)

    months_list = month_range_inclusive(sdate, edate)
    months_list = months_list[:12]
    months = len(months_list)

    if fixed_quantities is None or len(fixed_quantities) != months:
        fixed_quantities = [None]*months

    q, v = optimize_distribution(
        months=months,
        target_q=f8, target_v=f9,
        p1=p1, p2=p2, p3=p3, fee=fee, stamp=stamp,
        fixed_quantities=fixed_quantities,
        first_month_min_q=(d2 or 0.0),
        last_month_fixed_q=(c3 or 0.0)
    )

    return {
        "months": months_list,
        "F8": f8, "F9": f9,
        "F10": f10, "F11": f11,
        "q": q, "v": v
    }
