#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import posixpath
import sys
import typing
import threading

import openpyxl

import numpy as np

from download import download
from environ import pages_url


data_dir = os.path.dirname(__file__)


class Table(typing.NamedTuple):

    min_year: int
    max_year: int
    min_age: int
    max_age: int

    array: np.ndarray

    def mortality(self, year:int, age:int) -> float:
        year = max(year, self.min_year)
        year = min(year, self.max_year)
        assert age >= self.min_age
        if age > self.max_age:
            return 1.0
        return self.array[age - self.min_age, year - self.min_year]

    # https://www.ons.gov.uk/peoplepopulationandcommunity/healthandsocialcare/healthandlifeexpectancies/articles/lifeexpectancycalculator/2019-06-07
    def life_expectancy(self, year:int, age:int) -> float:
        yob = age - year
        p = 1.0
        le = 0.0
        for a in range(age, self.max_age, 1):
            year = yob + a
            m = self.mortality(year, age)
            p *= 1.0 - m
            le += p
        return le


def row_values(row:tuple[openpyxl.cell.cell.Cell|openpyxl.cell.cell.MergedCell,...]) -> list:
    return [field.value for field in row]


# Save a NPY atomically
def save_npy(dst:str, array:np.ndarray) -> None:
    dirname, basename = os.path.split(dst)
    tid = threading.get_native_id()
    tmp = os.path.join(dirname, f'.{basename}.{tid}')
    np.save(open(tmp, 'wb'), array)
    os.replace(tmp, dst)


# https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/bulletins/pastandprojecteddatafromtheperiodandcohortlifetables/2020baseduk1981to2070
# https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/datasets/mortalityratesqxprincipalprojectionenglandandwales
# https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/datasets/mortalityratesqxprincipalprojectionunitedkingdom
# TODO: Use or derive unisex tables?
def get_ons_table(basis:str, gender:str) -> Table:
    assert basis in ('period', 'cohort')
    assert gender in ('male', 'female')

    # XXX: Use UK mortality tables?
    url = 'https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/lifeexpectancies/datasets/mortalityratesqxprincipalprojectionenglandandwales/2020based/ewppp20qx.xlsx'
    filename = os.path.join(data_dir, posixpath.basename(url))

    min_year = 1981
    max_year = 2070
    min_age = 0
    max_age = 100
    num_age = max_age - min_age + 1

    wb = None
    npy = os.path.join(data_dir, f'mortality_{basis}_{gender}.npy')
    try:
        if "PYTEST_CURRENT_TEST" in os.environ:
            raise FileNotFoundError
        stream = open(npy, 'rb')
    except FileNotFoundError:
        if wb is None:
            download(url, filename, ttl=sys.maxsize, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            wb = openpyxl.load_workbook(filename, read_only=True, data_only=True)

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

        save_npy(npy, array)
    else:
        array = np.load(stream)

    table = Table(min_year=min_year, max_year=max_year, min_age=min_age, max_age=max_age, array=array)

    return table


# CMI unisex mortality rates for illustrations, published yearly at
# https://www.actuaries.org.uk/learn-and-develop/continuous-mortality-investigation/other-cmi-outputs/unisex-rates-0
class CmiEdition(typing.NamedTuple):

    url: str
    min_year: int

    basis: str = 'cohort'
    gender: str = 'unisex'
    min_age: int = 20
    max_age: int = 120

    @property
    def max_year(self) -> int:
        return self.min_year + 100

    @property
    def npy(self) -> str:
        return f'mortality_{self.basis}_{self.gender}_{self.min_year}.npy'

    # Parse the mortality rates from the original spreadsheet
    def parse(self) -> np.ndarray:
        filename = os.path.join(data_dir, posixpath.basename(self.url))

        num_year = self.max_year - self.min_year + 1
        num_age = self.max_age - self.min_age + 1

        download(self.url, filename, ttl=sys.maxsize, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        wb = openpyxl.load_workbook(filename, read_only=True, data_only=True)
        sheet_name = f'{self.min_year}-{(self.min_year + 1) % 100:02d}'
        sh = wb[sheet_name]

        header_cells, = sh.iter_rows(min_row=4, max_row=4)
        header_values = row_values(header_cells)
        assert header_values[0] == '[x]'
        assert header_values[1 : num_year + 1] == [year for year in range(self.min_year, self.max_year + 1)]

        data: list[list[float]] = []
        for row in sh.iter_rows(min_row=5, max_row=5 + num_age - 1):
            assert len(row) == len(header_cells)
            values = row_values(row)
            assert values[0] == self.min_age + len(data)
            data.append(values[1 : num_year + 1])

        assert len(data) == num_age

        return np.array(data, dtype=np.float32)

    # The NPY file is generated by main() and published to GitHub Pages by
    # .github/scripts/gh-pages.sh
    def get(self) -> Table:
        npy = os.path.join(data_dir, self.npy)
        download(pages_url + self.npy, npy)
        array = np.load(npy)

        return Table(min_year=self.min_year, max_year=self.max_year, min_age=self.min_age, max_age=self.max_age, array=array)


# All editions published to GitHub Pages, oldest first.
#
# Older editions are kept for a transitional period, so that the deployed app
# keeps working until GitHub Pages is updated with the newest edition, and can
# be removed afterwards.
#
# Keep in sync with the CMI spreadsheet caches in .github/workflows/*.yml
cmi_editions = [
    # https://www.actuaries.org.uk/system/files/field/document/Unisex%20mortality%20rates%20for%202026-2027%20illustrations%20v01%202025-10-17_0.xlsx
    CmiEdition('https://web.archive.org/web/20260517234707if_/https://www.actuaries.org.uk/system/files/field/document/Unisex%20mortality%20rates%20for%202026-2027%20illustrations%20v01%202025-10-17_0.xlsx', 2026),
    # https://www.actuaries.org.uk/system/files/field/document/Unisex%20mortality%20rates%20for%202027-2028%20illustrations%20v01%202026-10-14.xlsx
    CmiEdition('https://web.archive.org/web/20261121083855if_/https://www.actuaries.org.uk/system/files/field/document/Unisex%20mortality%20rates%20for%202027-2028%20illustrations%20v01%202026-10-14.xlsx', 2027),
]
# The edition used by the app.  Only switch to the newest edition once GitHub
# Pages has been updated with it.
cmi_edition = cmi_editions[-1]


def get_cmi_table() -> Table:
    return cmi_edition.get()


# Generate the NPY files published to GitHub Pages by .github/scripts/gh-pages.sh
def main() -> None:
    dst_dir = sys.argv[1] if len(sys.argv) > 1 else data_dir
    for edition in cmi_editions:
        save_npy(os.path.join(dst_dir, edition.npy), edition.parse())


if __name__ == '__main__':
    main()
