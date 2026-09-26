def pessoa_na_zona(caixa_pessoa, zona, modo):
    x1, y1, x2, y2 = caixa_pessoa
    zx1, zy1, zx2, zy2 = zona

    if modo == "pes":
        px = (x1 + x2) / 2
        py = y2
        return zx1 <= px <= zx2 and zy1 <= py <= zy2
    else:
        return not (x2 < zx1 or x1 > zx2 or y2 < zy1 or y1 > zy2)