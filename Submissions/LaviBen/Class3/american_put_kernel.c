#include <math.h>
#include <stdint.h>
#include <stdlib.h>

/*
 * Exact recurrence used by american_put.py, with one contiguous rolling value
 * vector. Boundary output stores lattice indices only; Python reconstructs the
 * corresponding positive prices once per date.
 */
int american_put_kernel(
    double spot,
    double strike,
    double up,
    double down,
    double gross_rate,
    int64_t steps,
    int keep_boundary,
    double *out_value,
    int64_t *boundary_indices,
    uint64_t *out_node_updates
) {
    if (!isfinite(spot) || !isfinite(strike) || !isfinite(up) ||
        !isfinite(down) || !isfinite(gross_rate) || spot <= 0.0 ||
        strike < 0.0 || steps < 0 || !(0.0 < down && down < gross_rate &&
        gross_rate < up) || out_value == NULL || out_node_updates == NULL) {
        return 1;
    }
    double q = (gross_rate - down) / (up - down);
    if (!isfinite(q) || !(0.0 < q && q < 1.0)) {
        return 2;
    }
    if ((uint64_t)steps > (SIZE_MAX / sizeof(double)) - 1U) {
        return 3;
    }
    size_t count = (size_t)steps + 1U;
    double *values = (double *)calloc(count, sizeof(double));
    if (values == NULL) {
        return 4;
    }
    if (keep_boundary && boundary_indices == NULL) {
        free(values);
        return 5;
    }
    if (keep_boundary) {
        for (int64_t t = 0; t <= steps; ++t) {
            boundary_indices[t] = -1;
        }
    }

    double ratio = up / down;
    double up_weight = q / gross_rate;
    double down_weight = (1.0 - q) / gross_rate;
    double lowest_stock = spot;
    for (int64_t i = 0; i < steps; ++i) {
        lowest_stock *= down;
    }
    if (!isfinite(lowest_stock) || lowest_stock <= 0.0) {
        free(values);
        return 6;
    }

    double stock = lowest_stock;
    int64_t expiry_boundary = -1;
    for (int64_t j = 0; j <= steps; ++j) {
        double intrinsic = stock < strike ? strike - stock : 0.0;
        values[j] = intrinsic;
        if (intrinsic > 0.0) {
            expiry_boundary = j;
        }
        if (j < steps) {
            stock *= ratio;
        }
    }
    if (keep_boundary) {
        boundary_indices[steps] = expiry_boundary;
    }

    uint64_t node_updates = 0U;
    for (int64_t t = steps - 1; t >= 0; --t) {
        lowest_stock /= down;
        if (!isfinite(lowest_stock) || lowest_stock <= 0.0) {
            free(values);
            return 7;
        }
        stock = lowest_stock;
        int64_t row_boundary = -1;
        for (int64_t j = 0; j <= t; ++j) {
            double continuation =
                up_weight * values[j + 1] + down_weight * values[j];
            double intrinsic = stock < strike ? strike - stock : 0.0;
            if (intrinsic > 0.0 && intrinsic >= continuation) {
                values[j] = intrinsic;
                row_boundary = j;
            } else {
                values[j] = continuation;
            }
            if (j < t) {
                stock *= ratio;
            }
        }
        if (keep_boundary) {
            boundary_indices[t] = row_boundary;
        }
        node_updates += (uint64_t)(t + 1);
    }

    if (!isfinite(values[0]) || values[0] < 0.0) {
        free(values);
        return 8;
    }
    *out_value = values[0];
    *out_node_updates = node_updates;
    free(values);
    return 0;
}
