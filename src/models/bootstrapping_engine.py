from instruments import Instrument
from market_data import ZeroCouponCurve
from utils import nelson_siegel, nelson_siegel_svensson, display_grid
from .pricing_engine import DepositPricer, FuturePricer, SwapPricer
from scipy.optimize import curve_fit
from typing import Callable
import numpy as np
from numpy.typing import NDArray

deposit_pricer = DepositPricer()
future_pricer = FuturePricer()
swap_pricer = SwapPricer()

def update_curve(curve: ZeroCouponCurve, instrument) -> float:
    if instrument[0].name == "deposit":
        result = deposit_pricer.price(*instrument)
        curve.curve[deposit_pricer.maturity] = result
        return deposit_pricer.maturity

    elif instrument[0].name == "future":
        result = future_pricer.price(*instrument, curve.curve, curve.interpolation)
        curve.curve[future_pricer.maturity] = result
        return future_pricer.maturity
    
    else:
        unknown_dates, solution = swap_pricer.price(*instrument, curve.curve, curve.interpolation)
        for t, d in zip(unknown_dates, solution):
            curve.curve[t] = d
        return unknown_dates[-1] 

def bootstrap_curve(curve: ZeroCouponCurve, instruments: list[Instrument]) -> None:
    for instrument in instruments:
        print(f"⏳ Bootstrapping {instrument[0].name} with rate {instrument[1]:.4%}...")
        maturity = update_curve(curve, instrument)
        print(f"✅ Computed discount factor D({maturity:.3f}) = {curve.curve[maturity]:.6f} added to the curve.\n")
    print("🎯 Bootstrapping completed!\n")

def compute_curve(curve: ZeroCouponCurve) -> None:
    T_sorted = sorted(curve.curve.keys())
    curve.T = np.linspace(T_sorted[1], T_sorted[-1], 1000)
    curve.D = np.array([curve.interpolation(curve.curve, t) for t in curve.T])
    curve.ZC = -np.log(curve.D) / curve.T
    curve.FWD = -np.gradient(np.log(curve.D), curve.T)

def fit_curve(curve: ZeroCouponCurve, method: Callable) -> NDArray[np.float64]:
    bounds = {
        nelson_siegel: ([-1, -10, -10, 0.01], [10, 10, 10, 10]),
        nelson_siegel_svensson: ([-1, -10, -10, -10, 0.01, 0.01], [10, 10, 10, 10, 10, 10])
    }

    popt, _ = curve_fit(method, curve.T, curve.ZC, bounds=bounds[method])
    return popt

def adjust_curve(curve: ZeroCouponCurve, method: Callable) -> None:
    if method == nelson_siegel:
        curve.popt_ns = fit_curve(curve, method)
        curve.ZC_ns = method(curve.T, *curve.popt_ns)
        curve.D_ns = np.exp(-curve.ZC_ns * curve.T)
        curve.FWD_ns = -np.gradient(np.log(curve.D_ns), curve.T)
    elif method == nelson_siegel_svensson:
        curve.popt_nss = fit_curve(curve, method)
        curve.ZC_nss = method(curve.T, *curve.popt_nss)
        curve.D_nss = np.exp(-curve.ZC_nss * curve.T)
        curve.FWD_nss = -np.gradient(np.log(curve.D_nss), curve.T)

def create_curve(interpolation: Callable, instruments: list[Instrument]) -> ZeroCouponCurve:
    curve = ZeroCouponCurve(interpolation)
    bootstrap_curve(curve, instruments)
    compute_curve(curve)
    curve.popt_ns = fit_curve(curve, nelson_siegel)
    curve.popt_nss = fit_curve(curve, nelson_siegel_svensson)
    print("🔧 Adjusting curve with Nelson-Siegel and Nelson-Siegel-Svensson methods...\n")
    adjust_curve(curve, nelson_siegel)
    adjust_curve(curve, nelson_siegel_svensson)
    print("📈 Curve creation completed!\n")
    return curve

def display_bootstrap_result(curves: list[ZeroCouponCurve], legends: list[str]) -> None:
    display_grid([[curve.T for curve in curves] for _ in range(2)], [[curve.D for curve in curves], [curve.ZC for curve in curves]], ["Discount", "Zero-Coupon"], "Maturity", ["Discount", "Zero-Coupon", "Forward"], [legends, legends])

def display_adjusted_curve(curves: list[ZeroCouponCurve], legends: list[str]) -> None:
    display_grid([[curve.T for curve in curves] for _ in range(3)], [[curve.D_ns for curve in curves], [curve.ZC_ns for curve in curves], [curve.FWD_ns for curve in curves]], ["Discount NS", "Zero-Coupon NS", "Forward NS"], "Maturity", ["Discount NS", "Zero-Coupon NS", "Forward NS"], [legends, legends, legends])
    display_grid([[curve.T for curve in curves] for _ in range(3)], [[curve.D_nss for curve in curves], [curve.ZC_nss for curve in curves], [curve.FWD_nss for curve in curves]], ["Discount NSS", "Zero-Coupon NSS", "Forward NSS"], "Maturity", ["Discount NSS", "Zero-Coupon NSS", "Forward NSS"], [legends, legends, legends])