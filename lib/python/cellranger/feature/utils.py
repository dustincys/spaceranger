#!/usr/bin/env python
#
# Copyright (c) 2019 10X Genomics, Inc. All rights reserved.
#
# Utils for feature-barcoding technology

import numpy as np
import os
import json
import tenkit.safe_json as tk_safe_json


def get_gex_cell_list(filtered_barcodes):
    if not (all_files_present([filtered_barcodes])):
        raise ValueError("Filtered barcodes file not present")

    with open(filtered_barcodes) as f:
        lines = f.readlines()
        gex_cell_list = [line.split(",")[-1].strip() for line in lines]

    # In case of multiple-genomes, multiplets can lead to duplicates in gex_cell_list, because the genome is stripped away
    gex_cell_list = list(set(gex_cell_list))
    gex_cell_list.sort()
    return gex_cell_list


def check_if_none_or_empty(matrix):
    if matrix is None or matrix.get_shape()[0] == 0 or matrix.get_shape()[1] == 0:
        return True
    else:
        return False


def write_json_from_dict(input_dict, out_file_name):
    with open(out_file_name, "w") as f:
        json.dump(tk_safe_json.json_sanitize(input_dict), f, indent=4, sort_keys=True)


def write_csv_from_dict(input_dict, out_file_name, header=None):
    with open(out_file_name, "w") as f:
        if header is not None:
            f.write(header)
        for (key, value) in input_dict.iteritems():
            line = str(key) + "," + str(value) + "\n"
            f.write(line)


def get_depth_string(num_reads_per_cell):
    return str(np.round(float(num_reads_per_cell) / 1000, 1)) + "k"


def all_files_present(list_file_paths):
    if list_file_paths is None:
        return False

    files_none = [fpath is None for fpath in list_file_paths]
    if any(files_none):
        return False

    files_present = [os.path.isfile(fpath) for fpath in list_file_paths]

    if not (all(files_present)):
        return False

    return True
