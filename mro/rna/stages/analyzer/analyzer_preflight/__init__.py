#!/usr/bin/env python
#
# Copyright (c) 2019 10x Genomics, Inc. All rights reserved.
#
import martian
import math
import os

import cellranger.analysis.constants as analysis_constants
import cellranger.constants as cr_constants
import cellranger.matrix as cr_matrix
import cellranger.rna.library as rna_library

__MRO__ = """
stage ANALYZER_PREFLIGHT(
    in  bool  skip,
    in  h5    raw_matrices_h5,
    in  h5    filtered_matrices_h5,
    in  csv   use_genes,
    in  csv   exclude_genes,
    in  csv   use_bcs,
    in  int   num_analysis_bcs,
    in  int   force_cells,
    in  int   random_seed,
    in  int   num_pca_bcs,
    in  int   num_pca_genes,
    in  int   num_principal_comps,
    in  int   cbc_knn,
    in  float cbc_alpha,
    in  float cbc_sigma,
    in  bool  cbc_realign_panorama,
    in  int   max_clusters,
    in  int   graphclust_neighbors,
    in  float neighbor_a,
    in  float neighbor_b,
    in  int   tsne_perplexity,
    in  int   tsne_input_pcs,
    in  int   tsne_max_dims,
    in  int   tsne_max_iter,
    in  int   tsne_stop_lying_iter,
    in  int   tsne_mom_switch_iter,
    in  float tsne_theta,
    in  int   umap_n_neighbors,
    in  int   umap_input_pcs,
    in  int   umap_max_dims,
    in  float umap_min_dist,
    in  string umap_metric,
    out bool  skip,
    out bool  is_antibody_only,
    src py    "stages/analyzer/analyzer_preflight",
)
"""


def main(args, outs):
    #TODO: clean this up
    #pylint: disable=too-many-branches
    if args.skip:
        outs.skip = True
        return

    if not (args.filtered_matrices_h5 and os.path.exists(args.filtered_matrices_h5)):
        martian.exit("Filtered matrix does not exist: %s" % args.filtered_matrices_h5)

    flt_matrix_dims = cr_matrix.CountMatrix.load_dims_from_h5(args.filtered_matrices_h5)
    flt_genomes = cr_matrix.CountMatrix.get_genomes_from_h5(args.filtered_matrices_h5)

    # check for empty matrix
    nonzero_entries = flt_matrix_dims[2]
    if nonzero_entries == 0:
        martian.log_info("Gene-barcode matrix is empty - skipping analysis.")
        outs.skip = True
        return

    outs.is_antibody_only = False
    # check for presence of Gene Expression matrix
    library_types = cr_matrix.CountMatrix.load_library_types_from_h5_file(args.filtered_matrices_h5)
    if rna_library.GENE_EXPRESSION_LIBRARY_TYPE not in library_types and rna_library.ANTIBODY_LIBRARY_TYPE in library_types: # No GEX features found
        outs.is_antibody_only = True

    if args.raw_matrices_h5:
        if not os.path.exists(args.raw_matrices_h5):
            martian.exit("Raw matrix does not exist: %s" % args.raw_matrices_h5)
        raw_genomes = cr_matrix.CountMatrix.get_genomes_from_h5(args.raw_matrices_h5)
        if sorted(flt_genomes) != sorted(raw_genomes):
            martian.exit("Raw matrix genomes (%s) do not match filtered matrix genomes (%s)" % (raw_genomes, flt_genomes))

    if len(flt_genomes) > 1:
        martian.log_info("Matrix has multiple genomes - multi-genome analysis will be performed")
    elif len(flt_genomes) == 1:
        martian.log_info("Matrix has one genome - single-genome analysis will be performed")
    else:
        martian.log_info("Matrix has no genome - only antibody capture library detected")

    total_genes, total_bcs, _ = flt_matrix_dims

    # if we're using the defaults and the matrix doesn't have enough data, skip analysis
    if args.max_clusters is None and total_bcs < analysis_constants.MAX_N_CLUSTERS_DEFAULT:
        martian.log_info("Gene-barcode matrix is tiny (num_cells = %d) - skipping analysis." % total_bcs)
        outs.skip = True
        return
    if args.num_principal_comps is None and total_genes < analysis_constants.PCA_N_COMPONENTS_DEFAULT:
        martian.log_info("Gene-barcode matrix is tiny (num_genes = %d) - skipping analysis." % total_genes)
        outs.skip = True
        return

    # check force_cells
    if args.force_cells is not None:
        if args.use_bcs:
            martian.exit("Cannot specify both --barcodes and --force-cells in the same run.")
        if args.force_cells > total_bcs:
            martian.exit("Desired cell count (%d) is greater than the number of barcodes in the matrix (%d). Try passing in the raw (unfiltered) gene-barcode matrix instead." % (args.force_cells, total_bcs))
        total_bcs = args.force_cells

    # load barcode / gene lists
    if args.use_bcs:
        analysis_bcs = validate_csv(args.use_bcs, "barcodes", cr_constants.BARCODE_CSV_COLNAME)
    else:
        analysis_bcs = option(args.num_analysis_bcs, total_bcs)

    if args.use_genes:
        analysis_genes = validate_csv(args.use_genes, "genes", cr_constants.GENE_ID_CSV_COLNAME)
    else:
        analysis_genes = total_genes

    if args.exclude_genes:
        validate_csv(args.exclude_genes, "exclude_genes", cr_constants.GENE_ID_CSV_COLNAME)

    # get parameters or their defaults
    pca_bcs = option(args.num_pca_bcs, analysis_bcs)
    pca_genes = option(args.num_pca_genes, analysis_genes)
    pca_comps = option(args.num_principal_comps, analysis_constants.PCA_N_COMPONENTS_DEFAULT)
    max_clusters = option(args.max_clusters, analysis_constants.MAX_N_CLUSTERS_DEFAULT)
    graphclust_neighbors = option(args.graphclust_neighbors, analysis_constants.GRAPHCLUST_NEIGHBORS_DEFAULT)
    neighbor_a = option(args.neighbor_a, analysis_constants.GRAPHCLUST_NEIGHBOR_A_DEFAULT)
    neighbor_b = option(args.neighbor_b, analysis_constants.GRAPHCLUST_NEIGHBOR_B_DEFAULT)
    tsne_pcs = option(args.tsne_input_pcs, pca_comps)
    tsne_max_iter = option(args.tsne_max_iter, analysis_constants.TSNE_MAX_ITER)
    tsne_mom_switch_iter = option(args.tsne_mom_switch_iter, analysis_constants.TSNE_MOM_SWITCH_ITER)
    tsne_stop_lying_iter = option(args.tsne_stop_lying_iter, analysis_constants.TSNE_STOP_LYING_ITER)
    tsne_theta = option(args.tsne_theta, analysis_constants.TSNE_THETA)
    tsne_max_dims = option(args.tsne_max_dims, analysis_constants.TSNE_N_COMPONENTS)
    tsne_perplexity = option(args.tsne_perplexity, analysis_constants.TSNE_DEFAULT_PERPLEXITY)
    umap_pcs = option(args.umap_input_pcs, pca_comps)
    umap_min_dist = option(args.umap_min_dist, analysis_constants.UMAP_MIN_DIST)
    umap_max_dims = option(args.umap_max_dims, analysis_constants.UMAP_N_COMPONENTS)
    umap_n_neighbors = option(args.umap_n_neighbors, analysis_constants.UMAP_DEFAULT_N_NEIGHBORS)
    umap_metric = option(args.umap_metric, analysis_constants.UMAP_DEFAULT_METRIC)
    cbc_knn = option(args.cbc_knn, analysis_constants.CBC_KNN)
    cbc_alpha = option(args.cbc_alpha, analysis_constants.CBC_ALPHA)
    cbc_sigma = option(args.cbc_sigma, analysis_constants.CBC_SIGMA)

    # check constraints
    if not (total_bcs >= analysis_bcs >= pca_bcs >= max_clusters >= 2):
        martian.exit("""Parameters must satisfy total_bcs >= analysis_bcs >= pca_bcs >= max_clusters >= 2. Possible causes:
        * the matrix has too few barcodes for analysis
        * you passed bad parameter values when calling 'cellranger reanalyze'
        * you passed a barcode CSV file that's inconsistent with your matrix or analysis parameters""")

    if not (total_genes >= analysis_genes >= pca_genes >= pca_comps >= tsne_pcs >= 2 and pca_comps >= umap_pcs >= 2):
        martian.exit("""Parameters must satisfy:
        total_genes >= analysis_genes >= pca_genes >= pca_comps >= tsne_pcs >= 2 and pca_comps >= umap_pcs >= 2.
        Possible causes:
        * the matrix has too few genes for analysis (is your reference correct?)
        * you passed bad parameter values when calling 'cellranger reanalyze'
        * you passed a genes CSV file that's inconsistent with your matrix or analysis parameters""")

    if not (tsne_max_iter >= tsne_mom_switch_iter >= 1 and tsne_max_iter >= tsne_stop_lying_iter >= 1):
        martian.exit("Parameters must satisfy tsne_max_iter >= tsne_mom_switch_iter >= 1 and tsne_max_iter >= tsne_stop_lying_iter >= 1.")
    if not (0 <= tsne_theta <= 1):
        martian.exit("Parameter tsne_theta must lie between 0 and 1.")
    if not (tsne_max_dims in [2, 3]):
        martian.exit("Parameter tsne_max_dims must be 2 or 3.")
    if not (1 <= tsne_perplexity <= 500):
        martian.exit("Parameter tsne_perplexity must lie between 1 and 500.")
    if not (0 <= umap_min_dist <= 1):
        martian.exit("Parameter umap_min_dist must lie between 0 and 1.")
    if not (umap_max_dims in [2, 3]):
        martian.exit("Parameter umap_max_dims must be 2 or 3.")
    if umap_n_neighbors < 1:
        martian.exit("Parameter umap_n_neighbors must be greater than or equal 1.")

    umap_allowed_metric = ['euclidean', 'manhattan', 'chebyshev', 'minkowski', 'canberra', 'braycurtis',
                        'mahalanobis', 'wminkowski', 'seuclidean', 'cosine', 'correlation', 'haversine',
                        'hamming', 'jaccard', 'dice', 'russelrao', 'kulsinski', 'rogerstanimoto',
                        'sokalmichener', 'sokalsneath', 'yule']
    if umap_metric not in umap_allowed_metric:
        martian.exit("""
        Parameter umap_metric must be selected from the following:
        {}
        """.format(', '.join(umap_allowed_metric)))
    if not (max_clusters <= 50):
        martian.exit("Parameter max_clusters cannot be greater than 50.")
    if not (graphclust_neighbors >= 0):
        martian.exit("Parameter graphclust_neighbors cannot be less than zero.")
    if not (not math.isnan(neighbor_a) and not math.isinf(neighbor_a)):
        martian.exit("Parameter neighbor_a must be finite.")
    if not (neighbor_b >= 0):
        martian.exit("Parameter neighbor_b cannot be less than zero.")
    if not (5 <= cbc_knn <= 20):
        martian.exit("Parameter cbc_knn must lie between 5 and 20.")
    if not (0 <= cbc_alpha <= 0.5):
        martian.exit("Parameter cbc_alpha must lie between 0 and 0.5.")
    if not (10 <= cbc_sigma <= 500):
        martian.exit("Parameter cbc_sigma must lie between 10 and 500.")

    if not os.access(args.filtered_matrices_h5, os.R_OK):
        martian.exit("Filtered matrix file is not readable, please check file permissions: %s" % args.filtered_matrices_h5)

    outs.skip = False


def option(arg, default):
    return arg if arg is not None else default

def validate_csv(csv_file, entry_type, entry_colname):
    if not os.path.exists(csv_file):
        martian.exit("Specified %s file does not exist: %s" % (entry_type, csv_file))
    elif not os.access(csv_file, os.R_OK):
        martian.exit("Specified %s file is not readable, please check file permissions: %s" % (entry_type, csv_file))
    with open(csv_file) as f:
        header = f.readline().strip().split(',')
        if header[0] != entry_colname:
            martian.exit("First line of %s file must be a header line, with '%s' as the first column." % (entry_type, entry_colname))
        counts = sum(1 for line in f) # count remaining lines
    if counts == 0:
        martian.exit("Specified %s file must contain at least one entry." % entry_type)
    return counts
