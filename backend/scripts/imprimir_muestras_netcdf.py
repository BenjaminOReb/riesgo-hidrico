# imprimir_muestras_netcdf.py
import argparse
import os
import numpy as np
import xarray as xr
import cftime

def decode_time(ds, t_index):
    if "time" not in ds.coords:
        return ""
    t = ds["time"]
    try:
        units = t.attrs.get("units", None)
        cal   = t.attrs.get("calendar", "standard")
        if units is None:
            return str(t.values[t_index])
        dt = cftime.num2date(t.values[t_index], units=units, calendar=cal)
        return getattr(dt, "isoformat", lambda: str(dt))()
    except Exception:
        try:
            return str(t.values[t_index])
        except Exception:
            return ""

def take_2d(arr, t_index):
    """Devuelve un DataArray 2D (lat,lon) para el tiempo t_index si aplica."""
    if "time" in arr.dims:
        arr = arr.isel(time=t_index)
    # Reordenar a (lat, lon) si tiene ambos
    if set(["lat","lon"]).issubset(arr.dims):
        arr = arr.transpose("lat","lon")
    return arr

def main():
    ap = argparse.ArgumentParser(description="Imprime 10 muestras de un NetCDF (crudo o fuzzy).")
    ap.add_argument("path", help="Ruta al NetCDF")
    ap.add_argument("--vars", nargs="*", default=None,
                    help="Variables a mostrar (por defecto: todas las del dataset)")
    ap.add_argument("--time-index", type=int, default=-1,
                    help="Índice de tiempo (por defecto: último)")
    ap.add_argument("--n", type=int, default=10, help="Cantidad de muestras (default 10)")
    ap.add_argument("--method", choices=["random","sequential"], default="random",
                    help="Estrategia de muestreo de celdas válidas")
    ap.add_argument("--seed", type=int, default=42, help="Semilla aleatoria si method=random")
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(f"Archivo no encontrado: {args.path}")
        return

    ds = xr.open_dataset(args.path, decode_times=False)

    # Detectar coordenadas
    if "lat" not in ds.coords or "lon" not in ds.coords:
        print("Este dataset no tiene coords 'lat' y 'lon'.")
        ds.close()
        return

    # Variables a usar
    data_vars = list(ds.data_vars)
    if not data_vars:
        print("No hay variables de datos en el dataset.")
        ds.close()
        return
    if args.vars:
        missing = [v for v in args.vars if v not in data_vars]
        if missing:
            print(f"Variables no encontradas: {missing}")
            ds.close()
            return
        data_vars = args.vars

    # Preparar matrices 2D de todas las variables seleccionadas
    arrays = {}
    for v in data_vars:
        try:
            arr2d = take_2d(ds[v], args.time_index).values.astype(float)
            arrays[v] = arr2d
        except Exception as e:
            print(f"No se pudo extraer {v} en time_index={args.time_index}: {e}")
            ds.close()
            return

    # Construir máscara válida: celdas finitas en TODAS las variables
    valid = None
    for v, A in arrays.items():
        mask = np.isfinite(A)
        valid = mask if valid is None else (valid & mask)

    if valid is None or not np.any(valid):
        print("No hay celdas válidas (no NaN) para ese tiempo en las variables seleccionadas.")
        ds.close()
        return

    # Seleccionar 10 puntos
    ys, xs = np.where(valid)
    idxs = np.arange(ys.size)
    if args.method == "random":
        rng = np.random.default_rng(args.seed)
        rng.shuffle(idxs)
    idxs = idxs[:args.n]
    ys, xs = ys[idxs], xs[idxs]

    lats = ds["lat"].values
    lons = ds["lon"].values
    time_str = decode_time(ds, args.time_index) if "time" in ds.coords else ""

    # Imprimir tabla
    cols = ["lon","lat"]
    if time_str != "":
        cols.append("time")
    cols.extend(data_vars)

    # Encabezado
    print(f"\nArchivo: {args.path}")
    if "time" in ds.coords:
        print(f"Tiempo (time_index={args.time_index}): {time_str}")
    print("Columnas:", ", ".join(cols))
    print("-" * 80)

    # Filas
    for y, x in zip(ys, xs):
        row = [float(lons[x]), float(lats[y])]
        if time_str != "":
            row.append(time_str)
        for v in data_vars:
            row.append(float(arrays[v][y, x]))
        # Formato simple
        formatted = [f"{row[0]:9.4f}", f"{row[1]:8.4f}"]
        pos = 2
        if time_str != "":
            formatted.append(str(row[2]))
            pos = 3
        formatted += [f"{val:8.4f}" for val in row[pos:]]
        print("  ".join(formatted))

    ds.close()

if __name__ == "__main__":
    main()
