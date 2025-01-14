#!/usr/bin/env python
#
# Copyright (c) 2015 10X Genomics, Inc. All rights reserved.
#
import cellranger.report as cr_report
import cellranger.utils as cr_utils

__MRO__ = """
stage SUMMARIZE_BASIC_REPORTS(
    in  json   extract_reads_summary,
    in  path   reference_path,
    in  map    align,
    in  json   attach_bcs_and_umis_summary,
    in  json   mark_duplicates_summary,
    in  json   count_genes_reporter_summary,
    in  json   filter_barcodes_summary,
    in  json   subsample_molecules_summary,
    in  json   report_molecules_summary,
    in  string barcode_whitelist,
    in  int[]  gem_groups,
    out json   summary,
    src py     "stages/counter/summarize_basic_reports",
) using (
    mem_gb   = 2,
    volatile = strict,
)
"""

def main(args, outs):
    summary_files = [
        args.extract_reads_summary,
        args.attach_bcs_and_umis_summary,
        args.mark_duplicates_summary,
        args.count_genes_reporter_summary,
        args.filter_barcodes_summary,
        args.subsample_molecules_summary,
        args.report_molecules_summary
    ]

    cr_report.merge_jsons(summary_files, outs.summary, [cr_utils.build_alignment_param_metrics(args.align)])
