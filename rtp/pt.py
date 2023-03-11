# https://www.comparaja.pt/blog/escaloes-irs
income_tax_bands = [
   ( 7479, 0.145),
   (11284, 0.210),
   (15992, 0.265),
   (20700, 0.285),
   (26355, 0.350),
   (38632, 0.370),
   (50483, 0.435),
   (78834, 0.450),
   (None,  0.480),
]

cgt_rate = 0.28

def net_income_pt(gross_income):
    tax = 0
    lbound = 0
    for ubound, rate in income_tax_bands:
        delta = max(gross_income - lbound, 0)
        if ubound is not None:
            delta = min(delta, ubound - lbound)
        tax += delta * rate
        lbound = ubound
    assert tax <= gross_income
    return gross_income - tax
