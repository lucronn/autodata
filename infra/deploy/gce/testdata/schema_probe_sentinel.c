/* Fixture only. Build against the explicitly selected PG17 development headers. */
#include "postgres.h"
#include "fmgr.h"
#include "utils/builtins.h"
#include "utils/fmgrprotos.h"
#include "foreign/fdwapi.h"

PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(probe_heap);
Datum probe_heap(PG_FUNCTION_ARGS) {
    ereport(WARNING, (errmsg("AUTODATA_PROBE_SENTINEL:heap")));
    return heap_tableam_handler(fcinfo);
}
PG_FUNCTION_INFO_V1(probe_btree);
Datum probe_btree(PG_FUNCTION_ARGS) {
    ereport(WARNING, (errmsg("AUTODATA_PROBE_SENTINEL:btree")));
    return bthandler(fcinfo);
}
PG_FUNCTION_INFO_V1(probe_fdw);
Datum probe_fdw(PG_FUNCTION_ARGS) {
    ereport(WARNING, (errmsg("AUTODATA_PROBE_SENTINEL:fdw")));
    ereport(ERROR, (errmsg("fixture foreign access refused")));
    PG_RETURN_NULL();
}
PG_FUNCTION_INFO_V1(probe_input);
Datum probe_input(PG_FUNCTION_ARGS) { return textin(fcinfo); }
PG_FUNCTION_INFO_V1(probe_output);
Datum probe_output(PG_FUNCTION_ARGS) {
    ereport(WARNING, (errmsg("AUTODATA_PROBE_SENTINEL:output")));
    return textout(fcinfo);
}
PG_FUNCTION_INFO_V1(probe_text);
Datum probe_text(PG_FUNCTION_ARGS) {
    ereport(WARNING, (errmsg("AUTODATA_PROBE_SENTINEL:expression")));
    PG_RETURN_TEXT_P(PG_GETARG_TEXT_PP(0));
}
PG_FUNCTION_INFO_V1(probe_predicate);
Datum probe_predicate(PG_FUNCTION_ARGS) {
    ereport(WARNING, (errmsg("AUTODATA_PROBE_SENTINEL:predicate")));
    PG_RETURN_BOOL(true);
}
PG_FUNCTION_INFO_V1(probe_cmp);
Datum probe_cmp(PG_FUNCTION_ARGS) {
    ereport(WARNING, (errmsg("AUTODATA_PROBE_SENTINEL:compare")));
    return bttextcmp(fcinfo);
}
