#!/usr/bin/env python
#
# Copyright (c) 2015 10X Genomics, Inc. All rights reserved.
#
# 1) Locate and identify all the input FASTQs.
# 2) For `cellranger count`, autodetect the chemistry version (for 3')
#      or sequencing configuration (for 5').

import gzip
import martian
import os
import tenkit.bam as tk_bam
import tenkit.fasta as tk_fasta
import tenkit.preflight as tk_preflight
import cellranger.chemistry as cr_chem
import cellranger.constants as cr_constants
import cellranger.rna.library as rna_library
import cellranger.h5_constants as h5_constants
import cellranger.fastq as cr_fastq
import cellranger.sample_def as cr_sample_def

__MRO__ = '''
stage SETUP_CHUNKS(
    in  string sample_id,
    in  map[]  sample_def,
    in  string[] library_type_filter,
    in  string chemistry_name,
    in  map    custom_chemistry_def,
    in  string default_library_type,
    out map[]  chunks,
    out map    chemistry_def,
    out string barcode_whitelist,
    out map[]  library_info,
    src py     "stages/common/setup_chunks",
)
'''

def validate_fastq_lists(filename_lists):
    """ Return true if sample indices found """
    if set(filename_lists.keys()) != set(cr_constants.FASTQ_READ_TYPES.keys()):
        martian.log_info('Read types specified: ' + ','.join(sorted(filename_lists.keys())))
        martian.log_info('Read types expected: ' + ','.join(sorted(cr_constants.FASTQ_READ_TYPES.keys())))
        martian.exit('Not all read types were specified. Exiting pipeline.')

    if len(filename_lists.values()[0]) == 0:
        return False

    if not all(len(filename_list) == len(filename_lists.values()[0]) for filename_list in filename_lists.itervalues()):
        for read_type, read_description in cr_constants.FASTQ_READ_TYPES.iteritems():
            martian.log_info('%s has a total of %s files: %s.' % (read_description, len(filename_lists[read_type]), str(filename_lists[read_type])))
        martian.exit('FASTQ files differ in number. Exiting pipeline.')
    return True

def construct_chunks(filename_lists,
                     sample_id, gem_group, library_id,
                     reads_interleaved, chemistry, library_type,
                     subsample_rate, target_set_name):
    """ filename_lists (list of dict<str,list>) """
    chunks = []

    for chunk_idx in xrange(len(filename_lists.values()[0])):
        chunk = {
            'gem_group': gem_group,
            'library_type': library_type,
            'library_id': library_id,
            'reads_interleaved': reads_interleaved,
            'read_chunks': {},
            'chemistry': chemistry,
            'subsample_rate': subsample_rate,
            'target_set_name': target_set_name,
        }

        for read_type in cr_constants.FASTQ_READ_TYPES.keys():
            filename = filename_lists[read_type][chunk_idx]
            chunk['read_chunks'][read_type] = filename

        # Build read group (@RG) string
        # Infer flowcell, lane from first fastq
        first_fastq = [fq for fq in chunk['read_chunks'].values() if fq is not None][0]
        flowcell, lane = tk_fasta.get_run_data(first_fastq)

        rg_string = tk_bam.pack_rg_string(sample_id, library_id,
                                          str(gem_group),
                                          flowcell, lane)
        chunk['read_group'] = rg_string

        chunks.append(chunk)

    return chunks

def fill_in_missing_reads(filename_lists):
    """ Provide a list of Nones for missing reads """
    max_filenames = max(len(filename_list) for filename_list in filename_lists.itervalues())
    for read_type, filename_list in filename_lists.iteritems():
        if len(filename_list) == 0:
            filename_lists[read_type] = [None] * max_filenames

def setup_chunks(sample_id, fq_spec, gem_group, library_id,
                 chemistry, library_type, subsample_rate,
                 target_set_name):
    """ Build chunks for a single sample def """
    chunks = []

    for _, group_spec in fq_spec.get_group_spec_iter():

        # Map internal read types to external (filename-based) readtypes
        read_type_map = cr_chem.get_read_type_map(chemistry, group_spec.fastq_mode)

        # Collect the fastq files for each read type
        filename_lists = {}
        for dest_read_type in cr_constants.FASTQ_READ_TYPES:
            src_read_type = read_type_map[dest_read_type]
            filename_lists[dest_read_type] = group_spec.get_fastqs(src_read_type)

        fill_in_missing_reads(filename_lists)

        if validate_fastq_lists(filename_lists):
            chunks += construct_chunks(filename_lists,
                                       sample_id=sample_id,
                                       gem_group=gem_group,
                                       library_id=library_id,
                                       reads_interleaved=group_spec.interleaved,
                                       chemistry=chemistry,
                                       library_type=library_type,
                                       subsample_rate=subsample_rate,
                                       target_set_name=target_set_name)
    return chunks

def main(args, outs):
    ok, msg = tk_preflight.check_gem_groups(args.sample_def)
    if not ok:
        martian.exit(msg)

    if args.chemistry_name is None:
        martian.exit("The chemistry was unable to be automatically determined. This can happen if not enough reads originate from the given reference. Please verify your choice of reference or explicitly specify the chemistry via the --chemistry argument.")

    if args.chemistry_name == cr_chem.CUSTOM_CHEMISTRY_NAME:
        chemistry = args.custom_chemistry_def
    else:
        chemistry = cr_chem.get_chemistry(args.chemistry_name)

    ## Build chunk dicts
    outs.chunks = []

    ## Assign library ids
    sample_defs = args.sample_def
    default_lib_type = args.default_library_type or rna_library.DEFAULT_LIBRARY_TYPE
    library_ids = cr_sample_def.assign_library_ids(sample_defs, default_lib_type)

    for sample_def, library_id in zip(sample_defs, library_ids):
        fq_spec = cr_fastq.FastqSpec.from_sample_def(sample_def)
        gem_group = cr_sample_def.get_gem_well(sample_def)
        library_type = cr_sample_def.get_library_type(sample_def) or default_lib_type
        subsample_rate = cr_sample_def.get_subsample_rate(sample_def)
        target_set_name = cr_sample_def.get_target_set_name(sample_def)

        chunks = setup_chunks(args.sample_id,
                              fq_spec,
                              gem_group,
                              library_id,
                              chemistry,
                              library_type,
                              subsample_rate,
                              target_set_name)

        if len(chunks) == 0:
            # No FASTQs found for a sample def
            martian.exit(cr_constants.NO_INPUT_FASTQS_MESSAGE)

        outs.chunks += chunks

    if len(outs.chunks) == 0:
        # No FASTQs found at all
        martian.exit(cr_constants.NO_INPUT_FASTQS_MESSAGE)

    ## Check the FASTQ files themselves
    check_chunk_fastqs(outs.chunks)

    ## Check the chemistry specifications
    check_chunk_chemistries(outs.chunks)

    ## Output chemistry and barcode whitelist
    outs.chemistry_def = outs.chunks[0]['chemistry']
    outs.barcode_whitelist = cr_chem.get_barcode_whitelist(outs.chemistry_def)

    ## Output library info
    lib_tuples = sorted(set((c['gem_group'],
                             c['library_id'],
                             c['library_type'],
                             c['target_set_name']) for c in outs.chunks))
    lib_info = []
    for g, i, t, s in lib_tuples:
        lib_info.append({
            'gem_group': g,
            'library_id': i,
            'library_type': t,
            rna_library.TARGET_SET_KEY: s
        })
    outs.library_info = lib_info

def check_fastq(fastq):
    # Check if fastq is readable
    if not os.access(fastq, os.R_OK):
        martian.exit("Do not have file read permission for FASTQ file: %s" % fastq)

    # Check if fastq is gzipped
    is_gzip_fastq = True
    try:
        with gzip.open(fastq) as f:
            f.read(1)
    except:
        is_gzip_fastq = False

    if is_gzip_fastq and not fastq.endswith(h5_constants.GZIP_SUFFIX):
        martian.exit("Input FASTQ file is gzipped but filename does not have %s suffix: %s" % (fastq, h5_constants.GZIP_SUFFIX))
    if not is_gzip_fastq and fastq.endswith(h5_constants.GZIP_SUFFIX):
        martian.exit("Input FASTQ file is not gzipped but filename has %s suffix: %s" % (fastq, h5_constants.GZIP_SUFFIX))

def check_chunk_fastqs(chunks):
    for chunk in chunks:
        for key in cr_constants.FASTQ_READ_TYPES:
            fastq = chunk.get(key)
            if fastq is not None:
                check_fastq(fastq)

def check_chunk_chemistries(chunks):
    """ Ensure all samples were generated with the same chemistry. """
    unique_chemistries = set([chunk['chemistry']['name'] for chunk in chunks])

    descriptions = map(cr_chem.get_chemistry_description_from_name, list(unique_chemistries))

    if len(unique_chemistries) > 1:
        martian.exit("Found multiple chemistries: %s. Combined analysis of libraries generated with different chemistries is not supported." % ', '.join(descriptions))
