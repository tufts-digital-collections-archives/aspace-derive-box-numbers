SELECT r.id,
       concat('["', group_concat(ao.component_id SEPARATOR '","'), '"]')
       FROM resource r
       INNER JOIN archival_object ao
         ON ao.root_record_id = r.id
       WHERE ao.component_id REGEXP '^[A-Z]{2}[0123456789]{3}[.][0123456789]{4,}.*'                  GROUP BY r.id
       ORDER BY r.id, ao.component_id
       INTO OUTFILE '/tmp/sequential_ao_cids_by_resource2.csv';
