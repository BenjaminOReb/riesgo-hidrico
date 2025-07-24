#!/usr/bin/env python3
"""
ncdump.py

Imprime por pantalla el “header” de un archivo NetCDF,
equivalente a la salida de `ncdump -h archivo.nc`.
"""

import sys
from netCDF4 import Dataset

def dump_header(nc_path):
    # Abrir en modo solo lectura
    ds = Dataset(nc_path, 'r')

    # GLOBAL ATTRIBUTES
    print(":: GLOBAL ATTRIBUTES ::\n")
    for name in ds.ncattrs():
        print(f"{name} = {ds.getncattr(name)!r}")
    print("\n:: DIMENSIONS ::\n")
    for dim_name, dim in ds.dimensions.items():
        length = len(dim) if not dim.isunlimited() else 'UNLIMITED'
        print(f"{dim_name}(size={length})")
    print("\n:: VARIABLES ::\n")
    for var_name, var in ds.variables.items():
        dims = ",".join(var.dimensions)
        dtype = var.dtype
        print(f"{dtype} {var_name}({dims})")
        # Mostrar sus atributos
        for attr in var.ncattrs():
            val = var.getncattr(attr)
            print(f"    :{attr} = {val!r}")
        print()

    ds.close()

def main():
    if len(sys.argv) != 2:
        print("Uso: python ncdump.py ruta_al_archivo.nc")
        sys.exit(1)

    nc_path = sys.argv[1]
    try:
        dump_header(nc_path)
    except Exception as e:
        print(f"Error leyendo {nc_path!r}: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
