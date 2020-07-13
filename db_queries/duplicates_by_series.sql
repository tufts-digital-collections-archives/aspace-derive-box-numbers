SELECT r.id,
       substr(r.identifier, 3, 5) as identifier,
       substr(ao.component_id, 7, 3) as series,
       tc.indicator,
       concat('{', group_concat(DISTINCT concat(tc.id, ': "', tc.barcode, '"')), '}') AS id2bc
  FROM resource r
  JOIN archival_object ao ON ao.root_record_id = r.id
  JOIN instance i ON i.archival_object_id = ao.id
  JOIN sub_container sc ON i.id = sc.instance_id
  JOIN top_container_link_rlshp tclr ON tclr.sub_container_id = sc.id
  JOIN top_container tc ON tc.id = tclr.top_container_id
  GROUP BY r.id, substr(ao.component_id, 7, 3), tc.indicator
  HAVING count(DISTINCT tc.id) > 1
  ORDER BY r.id, series, tc.indicator;
