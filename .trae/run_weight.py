import sys

sys.path.insert(0, "/home/fu/stock-slector")

from hikyuudata import importer

importer.import_weight()
print("WEIGHT_DONE")
