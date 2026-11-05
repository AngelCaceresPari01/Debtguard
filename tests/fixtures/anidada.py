def contar(a, b, c, d, e):
    r = 0
    for x in a:
        if x:
            for y in b:
                if y:
                    for z in c:
                        if z:
                            for w in d:
                                if w and e:
                                    r += 1
    return r
