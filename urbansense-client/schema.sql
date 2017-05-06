drop table if exists data;
create table data (
    id integer primary key autoincrement,
    time integer not null,
    lat real not null,
    lng real not null,
    value real not null,
    is_pothole boolean not null,
    sensor_name text not null
);

