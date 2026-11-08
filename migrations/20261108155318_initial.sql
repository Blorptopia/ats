create type application_status as enum ('pending', 'rejected', 'offer');
create table companies (
	id integer primary key generated always as identity,
	name text not null,
	banned bool not null default false
);
create table applications (
	id integer primary key generated always as identity,
	company_id integer not null references companies(id),
	applied_at date default now(),
	finn_ad_id integer,
	arbeidsplassen_post_id uuid,
	application_platform_url text,
	status application_status not null default 'pending'
);
create table interviews (
	id integer primary key generated always as identity,
	date date default now(),
	application_id integer not null references applications(id),
	note text not null default ''
);
