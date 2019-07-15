SELECT r.ead_id,
       tc.id,
       tc.barcode,
       count(ao.component_id),
       group_concat(ao.component_id)
  FROM top_container tc
  JOIN top_container_link_rlshp tclr
    ON tclr.top_container_id = tc.id
  JOIN sub_container s
    ON s.id = tclr.sub_container_id
  JOIN instance i
    ON s.instance_id = i.id
  JOIN archival_object ao
    ON ao.id = i.archival_object_id
  JOIN resource r
    ON ao.root_record_id = r.id
 WHERE tc.indicator LIKE 'data_value_missing%'
   AND tc.barcode like '%b' /* is a volume, presumably this is a safe and solid pre-req */
GROUP BY r.ead_id, tc.id
  HAVING count(DISTINCT right(ao.component_id, 4)) = 1 /* All our cids end in the same 4 chars */
ORDER BY tc.id, tc.barcode, ao.component_id
  INTO OUTFILE '/home/pobocks/blork/volumes.csv';
