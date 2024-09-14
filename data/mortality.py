#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import posixpath
import sys
import typing

import openpyxl

import numpy as np

from download import download


data_dir = os.path.dirname(__file__)


class Table(typing.NamedTuple):

    min_year: int
    max_year: int
    min_age: int
    max_age: int

    array: np.ndarray


tables: dict[str,dict[str,Table]] = {
    'period': {},
    'cohort': {},
}


def row_values(row:tuple[openpyxl.cell.cell.Cell, ...]) -> list:
    print(type(row))
    print(type(row[0]))
    return [field.value for field in row]


# https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/bulletins/pastandprojecteddatafromtheperiodandcohortlifetables/2020baseduk1981to2070
# https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/datasets/mortalityratesqxprincipalprojectionenglandandwales
# https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/datasets/mortalityratesqxprincipalprojectionunitedkingdom
def _load_ons_tables() -> None:
    # XXX: Use UK mortality tables?
    url = 'https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/datasets/mortalityratesqxprincipalprojectionenglandandwales/2020based/ewppp20qx.xlsx'
    filename = os.path.join(data_dir, posixpath.basename(url))

    min_year = 1981
    max_year = 2070
    min_age = 0
    max_age = 100
    num_age = max_age - min_age + 1

    wb = None
    for basis in ('period', 'cohort'):
        for gender in ('male', 'female'):
            npy = f'mortality_{basis}_{gender}.npy'
            try:
                if "PYTEST_CURRENT_TEST" in os.environ:
                    raise FileNotFoundError
                stream = open(os.path.join(data_dir, npy), 'rb')
            except FileNotFoundError:
                if wb is None:
                    download(url, filename, ttl=sys.maxsize, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    wb = openpyxl.load_workbook(filename)

                sh = wb[f'{gender}s {basis} qx']

                header_cells, = sh.iter_rows(min_row=5, max_row=5)
                header_values = row_values(header_cells)
                assert header_values[0] == 'age'
                assert header_values[1:] == [str(year) for year in range(min_year, max_year + 1)]

                data: list[list] = []
                for row in sh.iter_rows(min_row=6, max_row=6 + num_age - 1):
                    assert len(row) == len(header_cells)
                    values = row_values(row)
                    assert values[0] == min_age + len(data)
                    data.append(values[1:])

                assert len(data) == num_age

                array = np.array(data, dtype=np.float32)
                array /= 100000.0

                np.save(open(os.path.join(data_dir, '.' + npy), 'wb'), array)
                os.replace(os.path.join(data_dir, '.' + npy), os.path.join(data_dir, npy))
            else:
                array = np.load(stream)

            table = Table(min_year=min_year, max_year=max_year, min_age=min_age, max_age=max_age, array=array)
            tables[basis][gender] = table


_load_ons_tables()


# TODO: Use or derive unisex tables?
# See also:
# - https://www.actuaries.org.uk/learn-and-develop/continuous-mortality-investigation/other-cmi-outputs/unisex-rates-0
def _load_cmi_table() -> None:
    url = "https://www.actuaries.org.uk/system/files/field/document/Unisex%20mortality%20rates%20for%202024-2025%20illustrations%20v01%202023-12-13.xlsx"
    filename = os.path.join(data_dir, posixpath.basename(url))
    basis = 'cohort'
    gender = 'unisex'

    min_year = 2024
    max_year = 2124
    num_year = max_year - min_year + 1
    min_age = 20
    max_age = 120
    num_age = max_age - min_age + 1

    npy = f'mortality_{basis}_{gender}.npy'
    try:
        if "PYTEST_CURRENT_TEST" in os.environ:
            raise FileNotFoundError
        stream = open(os.path.join(data_dir, npy), 'rb')
    except FileNotFoundError:
        download(url, filename, ttl=sys.maxsize, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        wb = openpyxl.load_workbook(filename)
        sh = wb['2024-25']

        header_cells, = sh.iter_rows(min_row=4, max_row=4)
        header_values = row_values(header_cells)
        assert header_values[0] == '[x]'
        assert header_values[1 : num_year + 1] == [year for year in range(min_year, max_year + 1)]

        data: list[list[float]] = []
        for row in sh.iter_rows(min_row=5, max_row=5 + num_age - 1):
            assert len(row) == len(header_cells)
            values = row_values(row)
            assert values[0] == min_age + len(data)
            data.append(values[1 : num_year])

        assert len(data) == num_age

        array = np.array(data, dtype=np.float32)
        np.save(open(os.path.join(data_dir, '.' + npy), 'wb'), array)
        os.replace(os.path.join(data_dir, '.' + npy), os.path.join(data_dir, npy))
    else:
        array = np.load(stream)

    table = Table(min_year=min_year, max_year=max_year, min_age=min_age, max_age=max_age, array=array)
    tables[basis][gender] = table


_load_cmi_table()



def mortality(year:int, age:int, gender:str='unisex', basis:str='cohort') -> float:
    table = tables[basis][gender]
    year = max(year, table.min_year)
    year = min(year, table.max_year)
    assert age >= table.min_age
    if age > table.max_age:
        return 1.0
    return table.array[age - table.min_age, year - table.min_year]


# https://www.ons.gov.uk/peoplepopulationandcommunity/healthandsocialcare/healthandlifeexpectancies/articles/lifeexpectancycalculator/2019-06-07
def life_expectancy(year:int, age:int, gender:str, basis:str='period') -> float:
    yob = age - year
    table = tables[basis][gender]
    p = 1.0
    le = 0.0
    for a in range(age, table.max_age, 1):
        year = yob + a
        m = mortality(year, age, gender, basis)
        p *= 1.0 - m
        le += p
    return le
