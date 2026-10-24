/* Logical dump of a GnuCOBOL 3.2 INDEXED file (Berkeley DB btree), used by
 * the verifier to compare cobc's files with cobol2rust's own format: every
 * key/data pair in btree order (duplicates in stored order), each as a
 * little-endian u32 length followed by the bytes. */
#include <db.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>

static void put(const void *data, uint32_t size) {
    unsigned char length[4] = {size & 0xff, (size >> 8) & 0xff, (size >> 16) & 0xff, size >> 24};
    fwrite(length, 1, 4, stdout);
    fwrite(data, 1, size, stdout);
}

static int open_db(DB **db, const char *path, int duplicates) {
    if (db_create(db, NULL, 0) != 0) return 1;
    if (duplicates) (*db)->set_flags(*db, DB_DUP);
    if ((*db)->open(*db, NULL, path, NULL, DB_BTREE, DB_RDONLY, 0) != 0) {
        (*db)->close(*db, 0);
        return 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    DB *db;
    DBC *cursor;
    DBT key, data;
    if (argc != 2) { fprintf(stderr, "usage: bdb_dump FILE\n"); return 2; }
    if (open_db(&db, argv[1], 0) != 0 && open_db(&db, argv[1], 1) != 0) {
        fprintf(stderr, "bdb_dump: cannot open %s\n", argv[1]);
        return 1;
    }
    if (db->cursor(db, NULL, &cursor, 0) != 0) return 1;
    memset(&key, 0, sizeof key);
    memset(&data, 0, sizeof data);
    while (cursor->get(cursor, &key, &data, DB_NEXT) == 0) {
        put(key.data, key.size);
        put(data.data, data.size);
    }
    cursor->close(cursor);
    db->close(db, 0);
    return 0;
}
