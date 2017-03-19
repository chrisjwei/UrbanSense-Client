drop table if exists test;
create table test (
    id integer primary key autoincrement,
    time integer not null,
    lat real not null,
    lng real not null,
    value real not null
);
