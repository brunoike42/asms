SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'transport_student_assignment'
ORDER BY ordinal_position;
