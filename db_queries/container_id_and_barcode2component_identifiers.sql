SET group_concat_max_len=995000;
SELECT tc.id,
       tc.barcode,
       concat('[', group_concat(concat('"', ao.component_id, '"')), ']'),
       count(DISTINCT ao.root_record_id)
FROM top_container tc
JOIN top_container_link_rlshp tclr
  ON tclr.top_container_id = tc.id
JOIN sub_container s
  ON s.id = tclr.sub_container_id
JOIN instance i
  ON s.instance_id = i.id
JOIN archival_object ao
  ON ao.id = i.archival_object_id
WHERE tc.indicator LIKE 'data_value_missing%'
GROUP BY tc.indicator
ORDER BY tc.id, tc.barcode, ao.component_id
INTO OUTFILE '/home/pobocks/blork/id_barcode_aos.csv';
