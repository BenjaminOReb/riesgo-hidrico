#!/usr/bin/env python3
import os
import xarray as xr
import numpy as np

def inspect_dataset(path):
    print(f"\n📄 Archivo: {path}")
    if not os.path.exists(path):
        print(f"❌ No se encontró: {path}")
        return

    ds = xr.open_dataset(path, decode_times=False)
    vars = list(ds.data_vars)
    print("🔍 Variables disponibles:", vars)
    dims = dict(ds.dims)
    print("📏 Dimensiones:", dims)

    # Rango temporal si existe time
    if "time" in ds.dims:
        t0, t1 = ds["time"].values[0], ds["time"].values[-1]
        print(f"🕒 Rango de fechas: {t0} → {t1} ({ds.dims['time']} pasos)")

    # Para cada variable numérica calcula stats
    for var in vars:
        arr = ds[var].values.astype(float)
        # Contar válidos y NaN
        total = arr.size
        nan   = np.count_nonzero(np.isnan(arr))
        valid = total - nan
        mn    = np.nanmin(arr) if valid>0 else np.nan
        mx    = np.nanmax(arr) if valid>0 else np.nan
        mdn   = np.nanmean(arr) if valid>0 else np.nan
        pct   = 100. * valid / total if total>0 else 0
        print(f"▶ {var:12s}: shape={arr.shape}, válid={valid} ({pct:.1f}%), NaN={nan}")
        print(f"    min={mn:.3f}, max={mx:.3f}, mean={mdn:.3f}")

    ds.close()


if __name__ == "__main__":
    base = "uploads"

    # 1) NetCDF recortados
    
    archivos = [
        os.path.join(base, "recortado", "pr_2019-05_recortado.nc"),
        os.path.join(base, "recortado", "t2m_2019-05_recortado.nc"),
    ]
    # 2) NetCDF fuzzy (pr y t2m)
    archivos += [
        os.path.join(base, "fuzzy", fn)
        for fn in os.listdir(os.path.join(base, "fuzzy"))
        if fn.endswith(".nc")
    ]
    # 3) Índices de riesgo crisp y fuzzy
    archivos += [
        os.path.join(base, "riesgo_crisp", fn)
        for fn in os.listdir(os.path.join(base, "riesgo_crisp"))
        if fn.endswith(".nc")
    ]
    archivos += [
        os.path.join(base, "riesgo_fuzzy", fn)
        for fn in os.listdir(os.path.join(base, "riesgo_fuzzy"))
        if fn.endswith(".nc")
    ]
    archivos += [
        os.path.join(base, "crisp", "CR2MET_pr_v2.0_mon_1979_2019_005deg.nc"),
        os.path.join(base, "crisp","CR2MET_t2m_v2.0_mon_1979_2019_005deg.nc"),
    ]

    for path in archivos:
        inspect_dataset(path)
