"""
The Public Utility Data Liberation (PUDL) project core module.

The PUDL project integrates several different public data sets into one well
normalized database allowing easier access and interaction between all of them.
This module defines database tables using the SQLAlchemy Object Relational
Mapper (ORM) and initializes the database from several sources:

 - US Energy Information Agency (EIA):
   - Form 860 (eia860)
   - Form 861 (eia861)
   - Form 923 (eia923)
 - US Federal Energy Regulatory Commission (FERC):
   - Form 1 (ferc1)
   - Form 714 (ferc714)
 - US Environmental Protection Agency (EPA):
   - Air Market Program Data (epaampd)
   - Greenhouse Gas Reporting Program (epaghgrp)
"""

import pandas as pd
import numpy as np
import sqlalchemy as sa
import postgres_copy
import os.path


import eia923, ferc1, eia860
import settings
import models, models_eia923, models_eia860
import clean_ferc1, clean_pudl, clean_eia923

import constants as pc

###############################################################################
###############################################################################
# DATABASE CONNECTION & HELPER FUNCTIONS
###############################################################################
###############################################################################


def db_connect_pudl(testing=False):
    """Connect to the PUDL database using global settings from settings.py."""
    if(testing):
        return sa.create_engine(sa.engine.url.URL(**settings.DB_PUDL_TEST))
    else:
        return sa.create_engine(sa.engine.url.URL(**settings.DB_PUDL))


def create_tables_pudl(engine):
    """Create the tables associated with the PUDL Database."""
    models.PUDLBase.metadata.create_all(engine)


def drop_tables_pudl(engine):
    """Drop all the tables associated with the PUDL Database and start over."""
    models.PUDLBase.metadata.drop_all(engine)

###############################################################################
###############################################################################
#   OTHER HELPER FUNCTIONS
###############################################################################
###############################################################################


def csv_dump_load(df, table_name, engine, csvdir='', keep_csv=True):
    """
    Write a dataframe to CSV and load it into postgresql using COPY FROM.

    The fastest way to load a bunch of records is using the database's native
    text file copy function.  This function dumps a given dataframe out to a
    CSV file, and then loads it into the specified table using a sqlalchemy
    wrapper around the postgresql COPY FROM command, called postgres_copy.

    Args:
        df (pandas.DataFrame): The DataFrame which is to be dumped to CSV and
            loaded into the database. All DataFrame columns must have exactly
            the same names as the database fields they are meant to populate,
            and all column data types must be directly compatible with the
            database fields they are meant to populate. Do any cleanup before
            you call this function.
        table_name (str): The exact name of the database table which the
            DataFrame df is going to be used to populate. It will be used both
            to look up an SQLAlchemy table object in the PUDLBase metadata
            object, and to name the CSV file.
        engine (sqlalchemy.engine): SQLAlchemy database engine, which will be
            used to pull the CSV output into the database.
        csvdir (str): Path to the directory into which the CSV files should be
            output (and saved, if they are being kept).
        keep_csv (bool): True if the CSV output should be saved after the data
            has been loaded into the database. False if they should be deleted.

    Returns: Nothing.
    """
    import postgres_copy
    import os

    csvfile = os.path.join(csvdir, table_name + '.csv')
    df.to_csv(csvfile, index=False)
    tbl = models.PUDLBase.metadata.tables[table_name]
    postgres_copy.copy_from(open(csvfile, 'r'), tbl, engine,
                            columns=tuple(df.columns),
                            format='csv', header=True, delimiter=',')
    if not keep_csv:
        os.remove(csvfile)

###############################################################################
###############################################################################
#   BEGIN INGESTING STATIC & INFRASTRUCTURE TABLES
###############################################################################
###############################################################################


def ingest_static_tables(engine):
    """
    Populate static PUDL tables with constants for use as foreign keys.

    There are many values specified within the data that are essentially
    constant, but which we need to store for data validation purposes, for use
    as foreign keys.  E.g. the list of valid EIA fuel type codes, or the
    possible state and country codes indicating a coal delivery's location of
    origin. For now these values are primarily stored in a large collection of
    lists, dictionaries, and dataframes which are specified in the
    pudl.constants module.  This function uses those data structures to
    populate a bunch of small infrastructural tables within the PUDL DB.

    Args:
        engine (sqlalchemy.engine): A database engine with which to connect to
            to the PUDL DB.

    Returns: Nothing.
    """
    PUDL_Session = sa.orm.sessionmaker(bind=engine)
    pudl_session = PUDL_Session()

    # Populate tables with static data from above.
    pudl_session.add_all(
        [models.Fuel(name=f) for f in pc.ferc1_fuel_strings.keys()])
    pudl_session.add_all(
        [models.FuelUnit(unit=u) for u in pc.ferc1_fuel_unit_strings.keys()])
    pudl_session.add_all([models.Month(month=i + 1) for i in range(12)])
    pudl_session.add_all(
        [models.Quarter(q=i + 1, end_month=3 * (i + 1)) for i in range(4)])
    pudl_session.add_all(
        [models.PrimeMover(prime_mover=pm) for pm in pc.prime_movers])
    pudl_session.add_all(
        [models.RTOISO(abbr=k, name=v) for k, v in pc.rto_iso.items()])
    pudl_session.add_all([models.Year(year=yr) for yr in range(1994, 2017)])

    pudl_session.add_all([models.CensusRegion(abbr=k, name=v)
                          for k, v in pc.census_region.items()])
    pudl_session.add_all(
        [models.NERCRegion(abbr=k, name=v) for k, v in pc.nerc_region.items()])
    pudl_session.add_all(
        [models_eia923.RespondentFrequencyEIA923(abbr=k, unit=v)
         for k, v in pc.respondent_frequency_eia923.items()])
    pudl_session.add_all(
        [models_eia923.SectorEIA(id=k, name=v)
         for k, v in pc.sector_eia.items()])
    pudl_session.add_all(
        [models_eia923.ContractTypeEIA923(abbr=k, contract_type=v)
         for k, v in pc.contract_type_eia923.items()])
    pudl_session.add_all(
        [models_eia923.FuelTypeEIA923(abbr=k, fuel_type=v)
         for k, v in pc.fuel_type_eia923.items()])
    pudl_session.add_all(
        [models_eia923.PrimeMoverEIA923(abbr=k, prime_mover=v)
         for k, v in pc.prime_movers_eia923.items()])
    pudl_session.add_all(
        [models_eia923.FuelUnitEIA923(abbr=k, unit=v)
         for k, v in pc.fuel_units_eia923.items()])
    pudl_session.add_all(
        [models_eia923.FuelTypeAER(abbr=k, fuel_type=v)
         for k, v in pc.fuel_type_aer_eia923.items()])
    pudl_session.add_all(
        [models_eia923.FuelGroupEIA923(group=gr)
         for gr in pc.fuel_group_eia923])
    pudl_session.add_all(
        [models_eia923.EnergySourceEIA923(abbr=k, source=v)
         for k, v in pc.energy_source_eia923.items()])
    pudl_session.add_all(
        [models_eia923.CoalMineTypeEIA923(abbr=k, name=v)
         for k, v in pc.coalmine_type_eia923.items()])
    pudl_session.add_all(
        [models_eia923.CoalMineStateEIA923(abbr=k, state=v)
         for k, v in pc.coalmine_state_eia923.items()])
    pudl_session.add_all(
        [models_eia923.CoalMineStateEIA923(abbr=k, state=v)
         for k, v in pc.us_states.items()])  # is this right way to add these?
    pudl_session.add_all(
        [models_eia923.TransportModeEIA923(abbr=k, mode=v)
         for k, v in pc.transport_modes_eia923.items()])
    pudl_session.add_all(
        [models_eia923.NaturalGasTransportEIA923(abbr=k, status=v)
         for k, v in pc.natural_gas_transport_eia923.items()])
    pudl_session.add_all(
        [models_eia923.AERFuelCategoryEIA923(name=k)
         for k in pc.aer_fuel_type_strings.keys()])

    pudl_session.add_all([models.State(abbr=k, name=v)
                          for k, v in pc.us_states.items()])

    # Commit the changes to the DB and close down the session.
    pudl_session.commit()
    pudl_session.close_all()

    # We aren't bringing row_number in to the PUDL DB:
    ferc_accts_df = pc.ferc_electric_plant_accounts.drop('row_number', axis=1)
    # Get rid of excessive whitespace introduced to break long lines (ugh)
    ferc_accts_df.ferc_account_description = \
        ferc_accts_df.ferc_account_description.str.replace('\s+', ' ')

    ferc_accts_df.rename(columns={'ferc_account_id': 'id',
                                  'ferc_account_description': 'description'},
                         inplace=True)

    ferc_accts_df.to_sql('ferc_accounts',
                         con=engine, index=False, if_exists='append',
                         dtype={'id': sa.String,
                                'description': sa.String})

    ferc_depreciation_lines_df = \
        pc.ferc_accumulated_depreciation.drop('row_number', axis=1)

    ferc_depreciation_lines_df.\
        rename(columns={'line_id': 'id',
                        'ferc_account_description': 'description'},
               inplace=True)

    ferc_depreciation_lines_df.\
        to_sql('ferc_depreciation_lines',
               con=engine, index=False, if_exists='append',
               dtype={'id': sa.String,
                      'description': sa.String})


def ingest_glue_tables(engine):
    """
    Populate the tables which relate the EIA & FERC datasets to each other.

    We have compiled a bunch of information which can be used to map individual
    utilities and plants listed in both the EIA and FERC data sets to each
    other, allowing disparate data reported in the two sources to be related
    to each other. That data is primarily stored in the plant_output and
    utility_output tabs of results/id_mapping/mapping_eia923_ferc1.xlsx in the
    repository. There are a total of seven relations described in this data:

        - utilities: Unique id and name for each utility for use across the
          PUDL DB.
        - plants: Unique id and name for each plant for use across the PUDL DB.
        - utilities_eia923: EIA operator ids and names attached to a PUDL
          utility id.
        - plants_eia923: EIA plant ids and names attached to a PUDL plant id.
        - utilities_ferc1: FERC respondent ids & names attached to a PUDL
          utility id.
        - plants_ferc1: A combination of FERC plant names and respondent ids,
          associated with a PUDL plant ID. This is necessary because FERC does
          not provide plant ids, so the unique plant identifier is a
          combination of the respondent id and plant name.
        - util_plant_assn: An association table which describes which plants
          have relationships with what utilities. If a record exists in this
          table then combination of PUDL utility id & PUDL plant id does have
          an association of some kind. The nature of that association is
          somewhat fluid, and more scrutiny will likely be required for use in
          analysis.

    Presently, the 'glue' tables are a very basic piece of infrastructure for
    the PUDL DB, because they contain the primary key fields for utilities and
    plants. It may make sense to revise this going forward, as the
    relationships between data from different sources are looser than we had
    originally anticipated.
    """
    map_eia923_ferc1_file = os.path.join(settings.PUDL_DIR,
                                         'results',
                                         'id_mapping',
                                         'mapping_eia923_ferc1.xlsx')

    plant_map = pd.read_excel(map_eia923_ferc1_file, 'plants_output',
                              na_values='', keep_default_na=False,
                              converters={'plant_id': int,
                                          'plant_name': str,
                                          'respondent_id_ferc1': int,
                                          'respondent_name_ferc1': str,
                                          'plant_name_ferc1': str,
                                          'plant_id_eia923': int,
                                          'plant_name_eia923': str,
                                          'operator_name_eia923': str,
                                          'operator_id_eia923': int})

    utility_map = pd.read_excel(map_eia923_ferc1_file, 'utilities_output',
                                na_values='', keep_default_na=False,
                                converters={'utility_id': int,
                                            'utility_name': str,
                                            'respondent_id_ferc1': int,
                                            'respondent_name_ferc1': str,
                                            'operator_id_eia923': int,
                                            'operator_name_eia923': str})

    # We need to standardize plant names -- same capitalization and no leading
    # or trailing white space... since this field is being used as a key in
    # many cases. This also needs to be done any time plant_name is pulled in
    # from other tables.
    plant_map['plant_name_ferc1'] = plant_map['plant_name_ferc1'].str.strip()
    plant_map['plant_name_ferc1'] = plant_map['plant_name_ferc1'].str.title()

    plants = plant_map[['plant_id', 'plant_name']]
    plants = plants.drop_duplicates('plant_id')

    plants_eia923 = plant_map[['plant_id_eia923',
                               'plant_name_eia923',
                               'plant_id']]
    plants_eia923 = plants_eia923.drop_duplicates('plant_id_eia923')
    plants_ferc1 = plant_map[['plant_name_ferc1',
                              'respondent_id_ferc1',
                              'plant_id']]
    plants_ferc1 = plants_ferc1.drop_duplicates(['plant_name_ferc1',
                                                 'respondent_id_ferc1'])
    utilities = utility_map[['utility_id', 'utility_name']]
    utilities = utilities.drop_duplicates('utility_id')
    utilities_eia923 = utility_map[['operator_id_eia923',
                                    'operator_name_eia923',
                                    'utility_id']]
    utilities_eia923 = utilities_eia923.drop_duplicates('operator_id_eia923')

    utilities_ferc1 = utility_map[['respondent_id_ferc1',
                                   'respondent_name_ferc1',
                                   'utility_id']]
    utilities_ferc1 = utilities_ferc1.drop_duplicates('respondent_id_ferc1')

    # Now we need to create a table that indicates which plants are associated
    # with every utility.

    # These dataframes map our plant_id to FERC respondents and EIA
    # operators -- the equivalents of our "utilities"
    plants_respondents = plant_map[['plant_id', 'respondent_id_ferc1']]
    plants_operators = plant_map[['plant_id', 'operator_id_eia923']]

    # Here we treat the dataframes like database tables, and join on the
    # FERC respondent_id and EIA operator_id, respectively.
    utility_plant_ferc1 = utilities_ferc1.\
        join(plants_respondents.
             set_index('respondent_id_ferc1'),
             on='respondent_id_ferc1')

    utility_plant_eia923 = utilities_eia923.join(
        plants_operators.set_index('operator_id_eia923'),
        on='operator_id_eia923')

    # Now we can concatenate the two dataframes, and get rid of all the columns
    # except for plant_id and utility_id (which determine the  utility to plant
    # association), and get rid of any duplicates or lingering NaN values...
    utility_plant_assn = pd.concat([utility_plant_eia923, utility_plant_ferc1])
    utility_plant_assn = utility_plant_assn[['plant_id', 'utility_id']].\
        dropna().drop_duplicates()

    # At this point there should be at most one row in each of these data
    # frames with NaN values after we drop_duplicates in each. This is because
    # there will be some plants and utilities that only exist in FERC, or only
    # exist in EIA, and while they will have PUDL IDs, they may not have
    # FERC/EIA info (and it'll get pulled in as NaN)

    for df in [plants_eia923, plants_ferc1, utilities_eia923, utilities_ferc1]:
        assert df[pd.isnull(df).any(axis=1)].shape[0] <= 1
        df.dropna(inplace=True)

    # Before we start inserting records into the database, let's do some basic
    # sanity checks to ensure that it's (at least kind of) clean.
    # INSERT SANITY HERE

    # Any FERC respondent_id that appears in plants_ferc1 must also exist in
    # utils_ferc1:
    # INSERT MORE SANITY HERE

    plants.rename(columns={'plant_id': 'id', 'plant_name': 'name'},
                  inplace=True)
    plants.to_sql(name='plants',
                  con=engine, index=False, if_exists='append',
                  dtype={'id': sa.Integer, 'name': sa.String})

    utilities.rename(columns={'utility_id': 'id', 'utility_name': 'name'},
                     inplace=True)
    utilities.to_sql(name='utilities',
                     con=engine, index=False, if_exists='append',
                     dtype={'id': sa.Integer, 'name': sa.String})

    utilities_eia923.rename(columns={'operator_id_eia923': 'operator_id',
                                     'operator_name_eia923': 'operator_name',
                                     'utility_id': 'util_id_pudl'},
                            inplace=True)
    utilities_eia923.to_sql(name='utilities_eia923',
                            con=engine, index=False, if_exists='append',
                            dtype={'operator_id': sa.Integer,
                                   'operator_name': sa.String,
                                   'util_id_pudl': sa.Integer})

    utilities_ferc1.rename(columns={'respondent_id_ferc1': 'respondent_id',
                                    'respondent_name_ferc1': 'respondent_name',
                                    'utility_id': 'util_id_pudl'},
                           inplace=True)
    utilities_ferc1.to_sql(name='utilities_ferc1',
                           con=engine, index=False, if_exists='append',
                           dtype={'respondent_id': sa.Integer,
                                  'respondent_name': sa.String,
                                  'util_id_pudl': sa.Integer})

    plants_eia923.rename(columns={'plant_id_eia923': 'plant_id',
                                  'plant_name_eia923': 'plant_name',
                                  'plant_id': 'plant_id_pudl'},
                         inplace=True)
    plants_eia923.to_sql(name='plants_eia923',
                         con=engine, index=False, if_exists='append',
                         dtype={'plant_id': sa.Integer,
                                'plant_name': sa.String,
                                'plant_id_pudl': sa.Integer})

    plants_ferc1.rename(columns={'respondent_id_ferc1': 'respondent_id',
                                 'plant_name_ferc1': 'plant_name',
                                 'plant_id': 'plant_id_pudl'},
                        inplace=True)
    plants_ferc1.to_sql(name='plants_ferc1',
                        con=engine, index=False, if_exists='append',
                        dtype={'respondent_id': sa.Integer,
                               'plant_name': sa.String,
                               'plant_id_pudl': sa.Integer})

    utility_plant_assn.to_sql(name='util_plant_assn',
                              con=engine, index=False, if_exists='append',
                              dtype={'plant_id': sa.Integer,
                                     'utility_id': sa.Integer})


###############################################################################
###############################################################################
# BEGIN FERC 1 INGEST FUNCTIONS
###############################################################################
###############################################################################


def ingest_fuel_ferc1(pudl_engine, ferc1_engine, ferc1_years):
    """
    Clean & ingest f1_fuel table from FERC Form 1 DB into the PUDL DB.

    Read data from the f1_fuel table of our cloned FERC Form 1 database for
    the years specified by ferc1_years, clean it up and re-organize it for
    loading into the PUDL DB. This process includes converting some columns
    to be in terms of our preferred units, like MWh and mmbtu instead of kWh
    and btu. Plant names are also standardized (stripped & Title Case). Fuel
    and fuel unit strings are also standardized using our cleanstrings()
    function and string cleaning dictionaries found in pudl.constants.

    Args:
        pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
        ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
        ferc1_years (sequence of integers): Years for which we should extract
            fuel data from the FERC1 Database.

    Returns: Nothing.
    """
    # Grab the f1_fuel SQLAlchemy Table object from the metadata object.
    f1_fuel = ferc1.ferc1_meta.tables['f1_fuel']
    # Generate a SELECT statement that pulls all fields of the f1_fuel table,
    # but only gets records with plant names, and non-zero fuel amounts:
    f1_fuel_select = sa.sql.select([f1_fuel]).\
        where(f1_fuel.c.fuel != '').\
        where(f1_fuel.c.fuel_quantity > 0).\
        where(f1_fuel.c.plant_name != '').\
        where(f1_fuel.c.report_year.in_(ferc1_years))
    # Use the above SELECT to pull those records into a DataFrame:
    fuel_ferc1_df = pd.read_sql(f1_fuel_select, ferc1_engine)

    fuel_ferc1_df = clean_ferc1.clean_fuel_ferc1(fuel_ferc1_df)

    fuel_ferc1_df.to_sql(name='fuel_ferc1',
                         con=pudl_engine, index=False, if_exists='append',
                         dtype={'respondent_id': sa.Integer,
                                'report_year': sa.Integer})


def ingest_plants_steam_ferc1(pudl_engine, ferc1_engine, ferc1_years):
    """
    Clean f1_steam table of the FERC Form 1 DB and pull into the PUDL DB.

    Load data about large thermal plants from our cloned FERC Form 1 DB into
    the PUDL DB. Clean up and reorganize some of the information along the way.
    This includes converting to our preferred units of MWh and MW, as well as
    standardizing the strings describing the kind of plant and construction.

    Args:
        pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
        ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
        ferc1_years (sequence of integers): Years for which we should extract
            fuel data from the FERC1 Database.

    Returns: Nothing.
    """
    f1_steam = ferc1.ferc1_meta.tables['f1_steam']
    f1_steam_select = sa.sql.select([f1_steam]).\
        where(f1_steam.c.net_generation > 0).\
        where(f1_steam.c.plant_name != '').\
        where(f1_steam.c.report_year.in_(ferc1_years))

    ferc1_steam_df = pd.read_sql(f1_steam_select, ferc1_engine)
    # Discard DataFrame columns that we aren't pulling into PUDL:
    ferc1_steam_df.drop(['spplmnt_num', 'row_number', 'row_seq', 'row_prvlg',
                         'report_prd'], axis=1, inplace=True)

    # Standardize plant_name capitalization and remove leading/trailing white
    # space -- necesary b/c plant_name is part of many foreign keys.
    ferc1_steam_df['plant_name'] = ferc1_steam_df['plant_name'].str.strip()
    ferc1_steam_df['plant_name'] = ferc1_steam_df['plant_name'].str.title()

    # Take the messy free-form type_const and plant_kind fields, and do our
    # best to map them to some canonical categories...
    # this is necessarily imperfect:

    ferc1_steam_df.type_const = \
        clean_pudl.cleanstrings(ferc1_steam_df.type_const,
                                pc.ferc1_type_const_strings,
                                unmapped=np.nan)
    ferc1_steam_df.plant_kind = \
        clean_pudl.cleanstrings(ferc1_steam_df.plant_kind,
                                pc.ferc1_plant_kind_strings,
                                unmapped=np.nan)

    # Force the construction and installation years to be numeric values, and
    # set them to NA if they can't be converted. (table has some junk values)
    ferc1_steam_df['yr_const'] = pd.to_numeric(
        ferc1_steam_df['yr_const'],
        errors='coerce')
    ferc1_steam_df['yr_installed'] = pd.to_numeric(
        ferc1_steam_df['yr_installed'],
        errors='coerce')

    # Converting everything to per MW and MWh units...
    ferc1_steam_df['cost_per_mw'] = 1000 * ferc1_steam_df['cost_per_kw']
    ferc1_steam_df.drop('cost_per_kw', axis=1, inplace=True)
    ferc1_steam_df['net_generation_mwh'] = \
        ferc1_steam_df['net_generation'] / 1000
    ferc1_steam_df.drop('net_generation', axis=1, inplace=True)
    ferc1_steam_df['expns_per_mwh'] = 1000 * ferc1_steam_df['expns_kwh']
    ferc1_steam_df.drop('expns_kwh', axis=1, inplace=True)

    ferc1_steam_df.rename(columns={
        # FERC 1 DB Name      PUDL DB Name
        'yr_const': 'year_constructed',
        'yr_installed': 'year_installed',
        'tot_capacity': 'total_capacity_mw',
        'peak_demand': 'peak_demand_mw',
        'plnt_capability': 'plant_capability_mw',
        'when_limited': 'water_limited_mw',
        'when_not_limited': 'not_water_limited_mw',
        'avg_num_of_emp': 'avg_num_employees',
        'net_generation': 'net_generation_mwh',
        'cost_of_plant_to': 'cost_of_plant_total',
        'expns_steam_othr': 'expns_steam_other',
        'expns_engnr': 'expns_engineering',
        'tot_prdctn_expns': 'expns_production_total'},
        inplace=True)
    ferc1_steam_df.to_sql(name='plants_steam_ferc1',
                          con=pudl_engine, index=False, if_exists='append',
                          dtype={'respondent_id': sa.Integer,
                                 'report_year': sa.Integer,
                                 'type_const': sa.String,
                                 'plant_kind': sa.String,
                                 'year_constructed': sa.Integer,
                                 'year_installed': sa.Integer})


def ingest_plants_hydro_ferc1(pudl_engine, ferc1_engine, ferc1_years):
    """
    Ingest f1_hydro table of FERC Form 1 DB into PUDL DB.

    Load data about hydroelectric generation resources from our cloned FERC 1
    database into the PUDL DB. Standardizes plant names (stripping whitespace
    and Using Title Case).  Also converts into our preferred units of MW and
    MWh.

    Args:
        pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
        ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
        ferc1_years (sequence of integers): Years for which we should extract
            fuel data from the FERC1 Database.

    Returns: Nothing.
    """
    f1_hydro = ferc1.ferc1_meta.tables['f1_hydro']

    f1_hydro_select = sa.sql.select([f1_hydro]).\
        where(f1_hydro.c.plant_name != '').\
        where(f1_hydro.c.report_year.in_(ferc1_years))

    ferc1_hydro_df = pd.read_sql(f1_hydro_select, ferc1_engine)
    ferc1_hydro_df.drop(['spplmnt_num', 'row_number', 'row_seq', 'row_prvlg',
                         'report_prd'], axis=1, inplace=True)

    # Standardize plant_name capitalization and remove leading/trailing white
    # space -- necesary b/c plant_name is part of many foreign keys.
    ferc1_hydro_df['plant_name'] = ferc1_hydro_df['plant_name'].str.strip()
    ferc1_hydro_df['plant_name'] = ferc1_hydro_df['plant_name'].str.title()

    # Converting kWh to MWh
    ferc1_hydro_df['net_generation_mwh'] = \
        ferc1_hydro_df['net_generation'] / 1000.0
    ferc1_hydro_df.drop('net_generation', axis=1, inplace=True)
    # Converting cost per kW installed to cost per MW installed:
    ferc1_hydro_df['cost_per_mw'] = ferc1_hydro_df['cost_per_kw'] * 1000.0
    ferc1_hydro_df.drop('cost_per_kw', axis=1, inplace=True)
    # Converting kWh to MWh
    ferc1_hydro_df['expns_per_mwh'] = ferc1_hydro_df['expns_kwh'] * 1000.0
    ferc1_hydro_df.drop('expns_kwh', axis=1, inplace=True)

    ferc1_hydro_df['yr_const'] = pd.to_numeric(
        ferc1_hydro_df['yr_const'],
        errors='coerce')
    ferc1_hydro_df['yr_installed'] = pd.to_numeric(
        ferc1_hydro_df['yr_installed'],
        errors='coerce')
    ferc1_hydro_df.dropna(inplace=True)
    ferc1_hydro_df.rename(columns={
        # FERC1 DB          PUDL DB
        'project_no': 'project_number',
        'yr_const': 'year_constructed',
        'plant_const': 'plant_construction',
        'yr_installed': 'year_installed',
        'tot_capacity': 'total_capacity_mw',
        'peak_demand': 'peak_demand_mw',
        'plant_hours': 'plant_hours_connected_while_generating',
        'favorable_cond': 'net_capacity_favorable_conditions_mw',
        'adverse_cond': 'net_capacity_adverse_conditions_mw',
        'avg_num_of_emp': 'avg_number_employees',
        'cost_of_land': 'cost_land',
        'expns_engnr': 'expns_engineering',
        'expns_total': 'expns_production_total'
    }, inplace=True)

    ferc1_hydro_df.to_sql(name='plants_hydro_ferc1',
                          con=pudl_engine, index=False, if_exists='append',
                          dtype={'respondent_id': sa.Integer,
                                 'report_year': sa.Integer})


def ingest_plants_pumped_storage_ferc1(pudl_engine, ferc1_engine, ferc1_years):
    """
    Ingest f1_pumped_storage table of FERC Form 1 DB into PUDL DB.

    Load data about pumped hydro storage facilities from our cloned FERC 1
    database into the PUDL DB. Standardizes plant names (stripping whitespace
    and Using Title Case).  Also converts into our preferred units of MW and
    MWh.

    Args:
       pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
       ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
       ferc1_years (sequence of integers): Years for which we should extract
           fuel data from the FERC1 Database.

    Returns: Nothing.
    """
    f1_pumped_storage = ferc1.ferc1_meta.tables['f1_pumped_storage']

    # Removing the empty records.
    # This reduces the entries for 2015 from 272 records to 27.
    f1_pumped_storage_select = sa.sql.select([f1_pumped_storage]).\
        where(f1_pumped_storage.c.plant_name != '').\
        where(f1_pumped_storage.c.report_year.in_(ferc1_years))

    ferc1_pumped_storage_df = pd.read_sql(
        f1_pumped_storage_select, ferc1_engine)
    ferc1_pumped_storage_df.drop(['spplmnt_num', 'row_number', 'row_seq',
                                  'row_prvlg', 'report_prd'],
                                 axis=1, inplace=True)

    # Standardize plant_name capitalization and remove leading/trailing white
    # space -- necesary b/c plant_name is part of many foreign keys.
    ferc1_pumped_storage_df['plant_name'] = \
        ferc1_pumped_storage_df['plant_name'].str.strip()
    ferc1_pumped_storage_df['plant_name'] = \
        ferc1_pumped_storage_df['plant_name'].str.title()

    # Converting kWh to MWh
    ferc1_pumped_storage_df['net_generation_mwh'] = \
        ferc1_pumped_storage_df['net_generation'] / 1000.0
    ferc1_pumped_storage_df.drop('net_generation', axis=1, inplace=True)

    ferc1_pumped_storage_df['energy_used_for_pumping_mwh'] = \
        ferc1_pumped_storage_df['energy_used'] / 1000.0
    ferc1_pumped_storage_df.drop('energy_used', axis=1, inplace=True)

    ferc1_pumped_storage_df['net_load_mwh'] = \
        ferc1_pumped_storage_df['net_load'] / 1000.0
    ferc1_pumped_storage_df.drop('net_load', axis=1, inplace=True)

    # Converting cost per kW installed to cost per MW installed:
    ferc1_pumped_storage_df['cost_per_mw'] = \
        ferc1_pumped_storage_df['cost_per_kw'] * 1000.0
    ferc1_pumped_storage_df.drop('cost_per_kw', axis=1, inplace=True)

    ferc1_pumped_storage_df['expns_per_mwh'] = \
        ferc1_pumped_storage_df['expns_kwh'] * 1000.0
    ferc1_pumped_storage_df.drop('expns_kwh', axis=1, inplace=True)

    ferc1_pumped_storage_df['yr_const'] = pd.to_numeric(
        ferc1_pumped_storage_df['yr_const'],
        errors='coerce')
    ferc1_pumped_storage_df['yr_installed'] = pd.to_numeric(
        ferc1_pumped_storage_df['yr_installed'],
        errors='coerce')

    ferc1_pumped_storage_df.dropna(inplace=True)

    ferc1_pumped_storage_df.rename(columns={
        # FERC1 DB          PUDL DB
        'tot_capacity': 'total_capacity_mw',
        'project_no': 'project_number',
        'peak_demand': 'peak_demand_mw',
        'yr_const': 'year_constructed',
        'yr_installed': 'year_installed',
        'plant_hours': 'plant_hours_connected_while_generating',
        'plant_capability': 'plant_capability_mw',
        'avg_num_of_emp': 'avg_number_employees',
        'cost_wheels': 'cost_wheels_turbines_generators',
        'cost_electric': 'cost_equipment_electric',
        'cost_misc_eqpmnt': 'cost_equipment_misc',
        'cost_of_plant': 'cost_plant_total',
        'expns_water_pwr': 'expns_water_for_pwr',
        'expns_pump_strg': 'expns_pump_storage',
        'expns_misc_power': 'expns_generation_misc',
        'expns_misc_plnt': 'expns_misc_plant',
        'expns_producton': 'expns_producton_before_pumping',
        'tot_prdctn_exns': 'expns_producton_total'},
        inplace=True)

    ferc1_pumped_storage_df.to_sql(name='plants_pumped_storage_ferc1',
                                   con=pudl_engine, index=False,
                                   if_exists='append')


def ingest_accumulated_depreciation_ferc1(pudl_engine,
                                          ferc1_engine,
                                          ferc1_years):
    """
    Ingest f1_accumdepr_prvs table from FERC Form 1 DB into PUDL DB.

    Load data about accumulated depreciation from our cloned FERC Form 1
    database into the PUDL DB. This information is organized by FERC account,
    with each line of the FERC Form 1 having a different descriptive
    identifier like 'balance_end_of_year' or 'transmission'.

    Args:
       pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
       ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
       ferc1_years (sequence of integers): Years for which we should extract
           fuel data from the FERC1 Database.

    Returns: Nothing.
    """
    f1_accumdepr_prvsn = ferc1.ferc1_meta.tables['f1_accumdepr_prvsn']
    f1_accumdepr_prvsn_select = sa.sql.select([f1_accumdepr_prvsn]).\
        where(f1_accumdepr_prvsn.c.report_year.in_(ferc1_years))

    ferc1_apd_df = pd.read_sql(f1_accumdepr_prvsn_select, ferc1_engine)

    # Discard DataFrame columns that we aren't pulling into PUDL. For
    ferc1_apd_df.drop(['spplmnt_num', 'row_seq',
                       'row_prvlg', 'item', 'report_prd'],
                      axis=1, inplace=True)

    ferc1_acct_apd = pc.ferc_accumulated_depreciation.drop(
        ['ferc_account_description'], axis=1)
    ferc1_acct_apd.dropna(inplace=True)
    ferc1_acct_apd['row_number'] = ferc1_acct_apd['row_number'].astype(int)

    ferc1_accumdepr_prvsn_df = pd.merge(ferc1_apd_df, ferc1_acct_apd,
                                        how='left', on='row_number')
    ferc1_accumdepr_prvsn_df.drop('row_number', axis=1, inplace=True)

    ferc1_accumdepr_prvsn_df.\
        to_sql(name='accumulated_depreciation_ferc1',
               con=pudl_engine, index=False, if_exists='append',
               dtype={'respondent_id': sa.Integer,
                      'report_year': sa.Integer,
                      'line_id': sa.String,
                      'total_cde': sa.Numeric(14, 2),
                      'electric_plant': sa.Numeric(14, 2),
                      'future_plant': sa.Numeric(14, 2),
                      'leased plant': sa.Numeric(14, 2)})


def ingest_plant_in_service_ferc1(pudl_engine, ferc1_engine, ferc1_years):
    """
    Ingest f1_plant_in_srvce table of FERC Form 1 DB into PUDL DB.

    Load data about the financial value of utility plant in service from our
    cloned FERC Form 1 database into the PUDL DB. This information is organized
    by FERC account, with each line of the FERC Form 1 having a different FERC
    account id (most are numeric and correspond to FERC's Uniform Electric
    System of Accounts). As of PUDL v0.1, this data is only valid from 2007
    onward, as the line numbers for several accounts are different in earlier
    years.

    Args:
        pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
        ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
        ferc1_years (sequence of integers): Years for which we should extract
            fuel data from the FERC1 Database.

       Returns: Nothing.
    """
    min_yr = min(ferc1_years)
    assert min_yr >= 2007,\
        """Invalid year requested: {}. FERC Form 1 Plant In Service data is
        currently only valid for years 2007 and later.""".format(min_yr)
    f1_plant_in_srvce = ferc1.ferc1_meta.tables['f1_plant_in_srvce']
    f1_plant_in_srvce_select = sa.sql.select([f1_plant_in_srvce]).\
        where(f1_plant_in_srvce.c.report_year.in_(ferc1_years))

    ferc1_pis_df = pd.read_sql(f1_plant_in_srvce_select, ferc1_engine)

    # Discard DataFrame columns that we aren't pulling into PUDL. For the
    # Plant In Service table, we need to hold on to the row_number because it
    # corresponds to a FERC account number.
    ferc1_pis_df.drop(['spplmnt_num', 'row_seq', 'row_prvlg', 'report_prd'],
                      axis=1, inplace=True)

    # Now we need to add a column to the DataFrame that has the FERC account
    # IDs corresponding to the row_number that's already in there...
    ferc_accts_df = pc.ferc_electric_plant_accounts.drop(
        ['ferc_account_description'], axis=1)
    ferc_accts_df.dropna(inplace=True)
    ferc_accts_df['row_number'] = ferc_accts_df['row_number'].astype(int)

    ferc1_pis_df = pd.merge(ferc1_pis_df, ferc_accts_df,
                            how='left', on='row_number')
    ferc1_pis_df.drop('row_number', axis=1, inplace=True)

    ferc1_pis_df.rename(columns={
        # FERC 1 DB Name  PUDL DB Name
        'begin_yr_bal': 'beginning_year_balance',
        'addition': 'additions',
        'yr_end_bal': 'year_end_balance'},
        inplace=True)
    ferc1_pis_df.to_sql(name='plant_in_service_ferc1',
                        con=pudl_engine, index=False, if_exists='append',
                        dtype={'respondent_id': sa.Integer,
                               'report_year': sa.Integer,
                               'ferc_account_id': sa.String,
                               'beginning_year_balance': sa.Numeric(14, 2),
                               'additions': sa.Numeric(14, 2),
                               'retirements': sa.Numeric(14, 2),
                               'adjustments': sa.Numeric(14, 2),
                               'transfers': sa.Numeric(14, 2),
                               'year_end_balance': sa.Numeric(14, 2)})


def ingest_plants_small_ferc1(pudl_engine, ferc1_engine, ferc1_years):
    """
    Ingest f1_gnrt_plant table from our cloned FERC Form 1 DB into PUDL DB.

    This FERC Form 1 table contains information about a large number of small
    plants, including many small hydroelectric and other renewable generation
    facilities. Unfortunately the data is not well standardized, and so the
    plants have been categorized manually, with the results of that
    categorization stored in an Excel spreadsheet. This function reads in the
    plant type data from the spreadsheet and merges it with the rest of the
    information from the FERC DB based on record number, FERC respondent ID,
    and report year. When possible the FERC license number for small hydro
    plants is also manually extracted from the data.

    This categorization will need to be renewed with each additional year of
    FERC data we pull in. As of v0.1 the small plants have been categorized
    for 2004-2015.

    Args:
        pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
        ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
        ferc1_years (sequence of integers): Years for which we should extract
            fuel data from the FERC1 Database.

    Returns: Nothing.
    """
    import os.path
    from sqlalchemy import or_

    assert min(ferc1_years) >= 2004,\
        """Year {} is too early. Small plant data has not been categorized for
        before 2004.""".format(min(ferc1_years))
    assert max(ferc1_years) <= 2015,\
        """Year {} is too recent. Small plant data has not been categorized for
        any year 2015.""".format(max(ferc1_years))
    f1_small = ferc1.ferc1_meta.tables['f1_gnrt_plant']
    f1_small_select = sa.sql.select([f1_small, ]).\
        where(f1_small.c.report_year.in_(ferc1_years)).\
        where(f1_small.c.plant_name != '').\
        where(or_((f1_small.c.capacity_rating != 0),
                  (f1_small.c.net_demand != 0),
                  (f1_small.c.net_generation != 0),
                  (f1_small.c.plant_cost != 0),
                  (f1_small.c.plant_cost_mw != 0),
                  (f1_small.c.operation != 0),
                  (f1_small.c.expns_fuel != 0),
                  (f1_small.c.expns_maint != 0),
                  (f1_small.c.fuel_cost != 0)))

    ferc1_small_df = pd.read_sql(f1_small_select, ferc1_engine)

    # Standardize plant_name capitalization and remove leading/trailing white
    # space -- necesary b/c plant_name is part of many foreign keys.
    ferc1_small_df['plant_name'] = ferc1_small_df['plant_name'].str.strip()
    ferc1_small_df['plant_name'] = ferc1_small_df['plant_name'].str.title()

    ferc1_small_df['kind_of_fuel'] = ferc1_small_df['kind_of_fuel'].str.strip()
    ferc1_small_df['kind_of_fuel'] = ferc1_small_df['kind_of_fuel'].str.title()

    # Force the construction and installation years to be numeric values, and
    # set them to NA if they can't be converted. (table has some junk values)
    ferc1_small_df['yr_constructed'] = pd.to_numeric(
        ferc1_small_df['yr_constructed'],
        errors='coerce')
    # Convert from cents per mmbtu to dollars per mmbtu to be consistent
    # with the f1_fuel table data. Also, let's use a clearer name.
    ferc1_small_df['fuel_cost_per_mmbtu'] = ferc1_small_df['fuel_cost'] / 100.0
    ferc1_small_df.drop('fuel_cost', axis=1, inplace=True)

    # Create a single "record number" for the individual lines in the FERC
    # Form 1 that report different small plants, so that we can more easily
    # tell whether they are adjacent to each other in the reporting.
    ferc1_small_df['record_number'] = 46 * ferc1_small_df['spplmnt_num'] + \
        ferc1_small_df['row_number']

    # Unforunately the plant types were not able to be parsed automatically
    # in this table. It's been done manually for 2004-2015, and the results
    # get merged in in the following section.
    small_types_file = os.path.join(settings.PUDL_DIR,
                                    'results',
                                    'ferc1_small_plants',
                                    'small_plants_2004-2015.xlsx')
    small_types_df = pd.read_excel(small_types_file)

    # Only rows with plant_type set will give us novel information.
    small_types_df.dropna(subset=['plant_type', ], inplace=True)
    # We only need this small subset of the columns to extract the plant type.
    small_types_df = small_types_df[['report_year', 'respondent_id',
                                     'record_number', 'plant_name_clean',
                                     'plant_type', 'ferc_license']]

    # Munge the two dataframes together, keeping everything from the
    # frame we pulled out of the FERC1 DB, and supplementing it with the
    # plant_name_clean, plant_type, and ferc_license fields from our hand
    # made file.
    ferc1_small_df = pd.merge(ferc1_small_df,
                              small_types_df,
                              how='left',
                              on=['report_year',
                                  'respondent_id',
                                  'record_number'])

    # We don't need to pull these columns into PUDL, so drop them:
    ferc1_small_df.drop(['row_seq', 'row_prvlg', 'report_prd',
                         'row_number', 'spplmnt_num', 'record_number'],
                        axis=1, inplace=True)

    # Standardize plant_name capitalization and remove leading/trailing white
    # space, so that plant_name_clean matches formatting of plant_name
    ferc1_small_df['plant_name_clean'] = \
        ferc1_small_df['plant_name_clean'].str.strip()
    ferc1_small_df['plant_name_clean'] = \
        ferc1_small_df['plant_name_clean'].str.title()

    ferc1_small_df.rename(columns={
        # FERC 1 DB Name      PUDL DB Name
        'yr_constructed': 'year_constructed',
        'capacity_rating': 'total_capacity_mw',
        'net_demand': 'peak_demand_mw',
        'net_generation': 'net_generation_mwh',
        'plant_cost': 'cost_of_plant_total',
        'plant_cost_mw': 'cost_of_plant_per_mw',
        'operation': 'cost_of_operation',
        'expns_maint': 'expns_maintenance',
        'fuel_cost': 'fuel_cost_per_mmbtu'},
        inplace=True)
    ferc1_small_df.to_sql(name='plants_small_ferc1',
                          con=pudl_engine, index=False, if_exists='append',
                          dtype={'respondent_id': sa.Integer,
                                 'report_year': sa.Integer,
                                 'plant_name': sa.String,
                                 'plant_name_clean': sa.String,
                                 'plant_type': sa.String,
                                 'kind_of_fuel': sa.String,
                                 'ferc_license': sa.Integer,
                                 'year_constructed': sa.Integer,
                                 'total_capacity_mw': sa.Float,
                                 'peak_demand_mw': sa.Float,
                                 'net_generation_mwh': sa.Float,
                                 'cost_of_plant_total': sa.Numeric(14, 2),
                                 'cost_of_plant_per_mw': sa.Numeric(14, 2),
                                 'cost_of_operation': sa.Numeric(14, 2),
                                 'expns_fuel': sa.Numeric(14, 2),
                                 'expns_maintenance': sa.Numeric(14, 2),
                                 'fuel_cost_per_mmbtu': sa.Numeric(14, 2)})


def ingest_purchased_power_ferc1(pudl_engine, ferc1_engine, ferc1_years):
    """
    Ingest f1_purchased_pwr table from our cloned FERC Form 1 DB into PUDL DB.

    This function pulls FERC Form 1 data about inter-untility power purchases
    into the PUDL DB. This includes how much electricty was purchased, how
    much it cost, and who it was purchased from. Unfortunately the field
    describing which other utility the power was being bought from is poorly
    standardized, making it difficult to correlate with other data. It will
    need to be categorized by hand or with some fuzzy matching eventually.

    Args:
        pudl_engine (sqlalchemy.engine): Engine for connecting to the PUDL DB.
        ferc1_engine (sqlalchemy.engine): Engine for connecting to the FERC DB.
        ferc1_years (sequence of integers): Years for which we should extract
            fuel data from the FERC1 Database.

    Returns: Nothing.
    """
    f1_purchased_pwr = ferc1.ferc1_meta.tables['f1_purchased_pwr']
    f1_purchased_pwr_select = sa.sql.select([f1_purchased_pwr]).\
        where(f1_purchased_pwr.c.report_year.in_(ferc1_years))

    ferc1_purchased_pwr_df = pd.read_sql(f1_purchased_pwr_select, ferc1_engine)

    ferc1_purchased_pwr_df.drop(['spplmnt_num', 'row_number', 'row_seq',
                                 'row_prvlg', 'report_prd'],
                                axis=1, inplace=True)
    ferc1_purchased_pwr_df.replace(to_replace='', value=np.nan, inplace=True)
    ferc1_purchased_pwr_df.dropna(subset=['sttstcl_clssfctn',
                                          'rtsched_trffnbr'], inplace=True)

    ferc1_purchased_pwr_df.rename(columns={
        # FERC 1 DB Name  PUDL DB Name
        'athrty_co_name': 'authority_company_name',
        'sttstcl_clssfctn': 'statistical_classification',
        'rtsched_trffnbr': 'rate_schedule_tariff_number',
        'avgmth_bill_dmnd': 'average_billing_demand',
        'avgmth_ncp_dmnd': 'average_monthly_ncp_demand',
        'avgmth_cp_dmnd': 'average_monthly_cp_demand',
        'mwh_recv': 'mwh_received',
        'mwh_delvd': 'mwh_delivered',
        'dmnd_charges': 'demand_charges',
        'erg_charges': 'energy_charges',
        'othr_charges': 'other_charges',
        'settlement_tot': 'settlement_total'},
        inplace=True)

    ferc1_purchased_pwr_df.to_sql(
        name='purchased_power_ferc1',
        con=pudl_engine, index=False,
        if_exists='append',
        dtype={'respondent_id': sa.Integer,
               'report_year': sa.Integer,
               'authority_company_name': sa.String,
               'statistical_classification': sa.String,
               'rate_schedule_tariff_number': sa.String,
               'average_billing_demand': sa.String,
               'average_monthly_ncp_demand': sa.String,
               'average_monthly_cp_demand': sa.String,
               'mwh_purchased': sa.Numeric(14, 2),
               'mwh_received': sa.Numeric(14, 2),
               'mwh_delivered': sa.Numeric(14, 2),
               'demand_charges': sa.Numeric(14, 2),
               'energy_charges': sa.Numeric(14, 2),
               'other_charges': sa.Numeric(14, 2),
               'settlement_total': sa.Numeric(14, 2)})

###############################################################################
###############################################################################
# BEGIN EIA923 INGEST FUNCTIONS
###############################################################################
###############################################################################


def ingest_plant_info_eia923(pudl_engine, eia923_dfs,
                             csvdir='', keep_csv=True):
    """
    Ingest data describing static attributes of plants from EIA Form 923.

    Much of the static plant information is reported repeatedly, and scattered
    across several different pages of EIA 923. The data frame which this
    function uses is assembled from those many different pages, and passed in
    via the same dictionary of dataframes that all the other ingest functions
    use for uniformity.

    Populates the plant_info_eia923 table in the PUDL DB.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    plant_info_df = eia923_dfs['plant_frame'].copy()

    # There are other fields being compiled in the plant_info_df from all of
    # the various EIA923 spreadsheet pages. Do we want to add them to the
    # database model too? E.g. nameplate_capacity_mw, operator_name, etc.
    plant_info_df = plant_info_df[['plant_id',
                                   'combined_heat_power',
                                   'plant_state',
                                   'eia_sector',
                                   'naics_code',
                                   'reporting_frequency',
                                   'census_region',
                                   'nerc_region',
                                   'nameplate_capacity_mw']]

    # Since this is a plain Yes/No variable -- just make it a real sa.Boolean.
    plant_info_df.combined_heat_power.replace({'N': False, 'Y': True},
                                              inplace=True)

    # Get rid of excessive whitespace introduced to break long lines (ugh)
    plant_info_df.census_region = \
        plant_info_df.census_region.str.replace(' ', '')
    plant_info_df.drop_duplicates(subset='plant_id')

    plant_info_df['eia_sector'] = \
        clean_pudl.fix_int_na(plant_info_df['eia_sector'],
                              float_na=np.nan,
                              int_na=-1,
                              str_na='')

    plant_info_df['naics_code'] = \
        clean_pudl.fix_int_na(plant_info_df['naics_code'],
                              float_na=np.nan,
                              int_na=-1,
                              str_na='')

    plant_info_df['plant_id'] = plant_info_df['plant_id'].astype(int)

    csv_dump_load(plant_info_df, 'plant_info_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_generation_fuel_eia923(pudl_engine, eia923_dfs,
                                  csvdir='', keep_csv=True):
    """
    Ingest generation and fuel data from Page 1 of EIA Form 923 into PUDL DB.

    Page 1 of EIA 923 (in recent years) reports generation and fuel consumption
    on a monthly, per-plant basis.

    Populates the generation_fuel_eia923 table.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    # This needs to be a copy of what we're passed in so we can edit it.
    gf_df = eia923_dfs['generation_fuel'].copy()

    # Drop fields we're not inserting into the generation_fuel_eia923 table.
    cols_to_drop = ['combined_heat_power',
                    'plant_name',
                    'operator_name',
                    'operator_id',
                    'plant_state',
                    'census_region',
                    'nerc_region',
                    'naics_code',
                    'eia_sector',
                    'sector_name',
                    'fuel_unit',
                    'total_fuel_consumption_quantity',
                    'electric_fuel_consumption_quantity',
                    'total_fuel_consumption_mmbtu',
                    'elec_fuel_consumption_mmbtu',
                    'net_generation_megawatthours']
    gf_df.drop(cols_to_drop, axis=1, inplace=True)

    # Convert the EIA923 DataFrame from yearly to monthly records.
    gf_df = clean_eia923.yearly_to_monthly_eia923(gf_df, pc.month_dict_eia923)
    # Replace the EIA923 NA value ('.') with a real NA value.
    gf_df.replace(to_replace='^\.$', value=np.nan, regex=True, inplace=True)
    # Remove "State fuel-level increment" records... which don't pertain to
    # any particular plant (they have plant_id == operator_id == 99999)
    gf_df = gf_df[gf_df.plant_id != 99999]

    # Take a float field and make it an integer, with the empty sa.String
    # as the NA value... for postgres loading.
    gf_df['nuclear_unit_id'] = \
        clean_pudl.fix_int_na(gf_df['nuclear_unit_id'],
                              float_na=np.nan,
                              int_na=-1,
                              str_na='')

    # # map AER fuel types to simplified PUDL categories
    gf_df['aer_fuel_category'] = \
        clean_pudl.cleanstrings(gf_df.aer_fuel_type, pc.aer_fuel_type_strings)

    # Convert Year/Month columns into a single Date column...
    gf_df['report_date'] = pd.to_datetime({'year': gf_df.year,
                                           'month': gf_df.month,
                                           'day': 1})
    gf_df.drop(['year', 'month'], axis=1, inplace=True)

    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(gf_df, 'generation_fuel_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_plant_ownership_eia923(pudl_engine, eia923_dfs,
                                  csvdir='', keep_csv=True):
    """
    Ingest utility_id and plant_id data from Page 1 of EIA 923 into PUDL DB.

    Populates the plant_ownership_eia923 table.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    # This needs to be a copy of what we're passed in so we can edit it.
    po_df = eia923_dfs['generation_fuel'].copy()

    # Populate 'plant_ownership_eia923' table
    po_cols = ['plant_id', 'year', 'operator_id']
    po_df = po_df[po_cols]

    po_df = po_df.drop_duplicates(
        subset=['plant_id', 'year'])

    # Remove "State fuel-level increment" records... which don't pertain to
    # any particular plant (they have plant_id == operator_id == 99999)
    po_df = po_df[po_df.plant_id != 99999]

    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(po_df, 'plant_ownership_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_boilers_eia923(pudl_engine, eia923_dfs, csvdir='', keep_csv=True):
    """Ingest data on individual boilers from EIA Form 923.

    Populates the boilers_eia923 table.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    boilers_df = eia923_dfs['boiler_fuel'].copy()
    # Populate 'boilers_eia923' table
    boiler_cols = ['plant_id',
                   'boiler_id',
                   'prime_mover']
    boilers_df = boilers_df[boiler_cols]

    # drop null values from foreign key fields
    boilers_df.dropna(subset=['boiler_id', 'plant_id'], inplace=True)

    # We need to cast the boiler_id column as type str because sometimes
    # it is heterogeneous int/str which make drop_duplicates fail.
    boilers_df['boiler_id'] = boilers_df['boiler_id'].astype(str)
    boilers_df = boilers_df.drop_duplicates(
        subset=['plant_id', 'boiler_id'])

    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(boilers_df, 'boilers_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_boiler_fuel_eia923(pudl_engine, eia923_dfs,
                              csvdir='', keep_csv=True):
    """
    Ingest data on fuel consumption by boiler from EIA Form 923.

    Populates the boiler_fuel_eia923 table.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    bf_df = eia923_dfs['boiler_fuel'].copy()

    # Drop fields we're not inserting into the boiler_fuel_eia923 table.
    cols_to_drop = ['combined_heat_power',
                    'plant_name',
                    'operator_name',
                    'operator_id',
                    'plant_state',
                    'census_region',
                    'nerc_region',
                    'naics_code',
                    'eia_sector',
                    'sector_name',
                    'fuel_unit',
                    'total_fuel_consumption_quantity']
    bf_df.drop(cols_to_drop, axis=1, inplace=True)

    bf_df.dropna(subset=['boiler_id', 'plant_id'], inplace=True)

    # Convert the EIA923 DataFrame from yearly to monthly records.
    bf_df = clean_eia923.yearly_to_monthly_eia923(bf_df, pc.month_dict_eia923)
    # Replace the EIA923 NA value ('.') with a real NA value.
    bf_df.replace(to_replace='^\.$', value=np.nan, regex=True, inplace=True)

    # Convert Year/Month columns into a single Date column...
    bf_df['report_date'] = pd.to_datetime({'year': bf_df.year,
                                           'month': bf_df.month,
                                           'day': 1})
    bf_df.drop(['year', 'month'], axis=1, inplace=True)
    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(bf_df, 'boiler_fuel_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_generators_eia923(pudl_engine, eia923_dfs,
                             csvdir='', keep_csv=True):
    """
    Ingest data on individual generators from EIA Form 923.

    Populates the generators_eia923 table.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    # Populating the 'generators_eia923' table
    generators_df = eia923_dfs['generator'].copy()
    generator_cols = ['plant_id',
                      'generator_id',
                      'prime_mover']
    generators_df = generators_df[generator_cols]

    # drop null values from foreign key fields
    generators_df.dropna(subset=['generator_id', 'plant_id'], inplace=True)

    # We need to cast the generator_id column as type str because sometimes
    # it is heterogeneous int/str which make drop_duplicates fail.
    generators_df['generator_id'] = generators_df['generator_id'].astype(str)
    generators_df = generators_df.drop_duplicates(
        subset=['plant_id', 'generator_id'])

    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(generators_df, 'generators_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_generation_eia923(pudl_engine, eia923_dfs,
                             csvdir='', keep_csv=True):
    """
    Ingest data on generation by each generator from EIA Form 923.

    Populates the generation_eia923 table.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    # This needs to be a copy of what we're passed in so we can edit it.
    generation_df = eia923_dfs['generator'].copy()

    # Drop fields we're not inserting into the generation_eia923_fuel_eia923
    # table.
    cols_to_drop = ['combined_heat_power',
                    'plant_name',
                    'operator_name',
                    'operator_id',
                    'plant_state',
                    'census_region',
                    'nerc_region',
                    'naics_code',
                    'eia_sector',
                    'sector_name',
                    'net_generation_mwh_year_to_date']

    generation_df.dropna(subset=['generator_id'], inplace=True)

    generation_df.drop(cols_to_drop, axis=1, inplace=True)

    # Convert the EIA923 DataFrame from yearly to monthly records.
    generation_df = clean_eia923.yearly_to_monthly_eia923(
        generation_df, pc.month_dict_eia923)
    # Replace the EIA923 NA value ('.') with a real NA value.
    generation_df.replace(to_replace='^\.$', value=np.nan,
                          regex=True, inplace=True)

    # Convert Year/Month columns into a single Date column...
    generation_df['report_date'] = \
        pd.to_datetime({'year': generation_df.year,
                        'month': generation_df.month,
                        'day': 1})
    generation_df.drop(['year', 'month'], axis=1, inplace=True)
    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(generation_df, 'generation_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_coalmine_info_eia923(pudl_engine, eia923_dfs,
                                csvdir='', keep_csv=True):
    """
    Ingest data on coal mines supplying fuel from EIA Form 923.

    Populates the coalmine_info_eia923 table.  Also applies canonical
    categories across the different types of mines.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia923_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA923 form, as repoted in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    # These are the columns that we want to keep from FRC for the
    # coal mine info table.
    coalmine_cols = ['coalmine_name',
                     'coalmine_type',
                     'coalmine_state',
                     'coalmine_county',
                     'coalmine_msha_id']

    # Make a copy so we don't alter the FRC data frame... which we'll need
    # to use again for populating the FRC table (see below)
    cmi_df = eia923_dfs['fuel_receipts_costs'].copy()
    # Keep only the columns listed above:
    cmi_df = clean_eia923.coalmine_cleanup(cmi_df)

    cmi_df = cmi_df[coalmine_cols]

    # If we actually *have* an MSHA ID for a mine, then we have a totally
    # unique identifier for that mine, and we can safely drop duplicates and
    # keep just one copy of that mine, no matter how different all the other
    # fields associated with the mine info are... Here we split out all the
    # coalmine records that have an MSHA ID, remove them from the CMI
    # data frame, drop duplicates, and then bring the unique mine records
    # back into the overall CMI dataframe...
    cmi_with_msha = cmi_df[cmi_df['coalmine_msha_id'] > 0]
    cmi_with_msha = \
        cmi_with_msha.drop_duplicates(subset=['coalmine_msha_id', ])
    cmi_df.drop(cmi_df[cmi_df['coalmine_msha_id'] > 0].index)
    cmi_df.append(cmi_with_msha)

    cmi_df = cmi_df.drop_duplicates(subset=['coalmine_name',
                                            'coalmine_state',
                                            'coalmine_msha_id',
                                            'coalmine_type',
                                            'coalmine_county'])

    # drop null values if they occur in vital fields....
    cmi_df.dropna(subset=['coalmine_name', 'coalmine_state'], inplace=True)

    # Take a float field and make it an integer, with the empty sa.String
    # as the NA value... for postgres loading. Yes, this is janky.
    cmi_df['coalmine_msha_id'] = \
        clean_pudl.fix_int_na(cmi_df['coalmine_msha_id'],
                              float_na=np.nan,
                              int_na=-1,
                              str_na='')

    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(cmi_df, 'coalmine_info_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_fuel_receipts_costs_eia923(pudl_engine, eia923_dfs,
                                      csvdir='', keep_csv=True):
    """Ingest data on fuel purchases and costs from EIA Form 923."""
    frc_df = eia923_dfs['fuel_receipts_costs'].copy()

    # Drop fields we're not inserting into the fuel_receipts_costs_eia923
    # table.
    cols_to_drop = ['plant_name',
                    'plant_state',
                    'operator_name',
                    'operator_id',
                    'coalmine_msha_id',
                    'coalmine_type',
                    'coalmine_state',
                    'coalmine_county',
                    'coalmine_name',
                    'regulated',
                    'reporting_frequency']

    cmi_df = pd.read_sql('''SELECT * FROM coalmine_info_eia923''', pudl_engine)
    # In order for the merge to work, we need to get the coalmine_county field
    # back into ready-to-dump form... so it matches the types of the
    # coalmine_county field that we are going to be merging on in the frc_df.
    cmi_df['coalmine_county'] = \
        clean_pudl.fix_int_na(cmi_df['coalmine_county'])
    cmi_df = cmi_df.rename(columns={'id': 'coalmine_id'})

    # This type/naming cleanup function is separated out so that we can be
    # sure it is applied exactly the same both when the coalmine_info table
    # is populated, and here (since we need them to be identical for the
    # following merge)
    frc_df = clean_eia923.coalmine_cleanup(frc_df)
    frc_df = frc_df.merge(cmi_df, how='left',
                          on=['coalmine_name',
                              'coalmine_state',
                              'coalmine_msha_id',
                              'coalmine_type',
                              'coalmine_county'])

    frc_df.drop(cols_to_drop, axis=1, inplace=True)

    # Replace the EIA923 NA value ('.') with a real NA value.
    frc_df.replace(to_replace='^\.$', value=np.nan, regex=True, inplace=True)

    # These come in ALL CAPS from EIA...
    frc_df['supplier'] = frc_df['supplier'].astype(str).str.strip()
    frc_df['supplier'] = frc_df['supplier'].astype(str).str.title()

    # Standardize case on transportaion codes -- all upper case!
    frc_df['primary_transportation_mode'] = \
        frc_df['primary_transportation_mode'].str.upper()
    frc_df['secondary_transportation_mode'] = \
        frc_df['secondary_transportation_mode'].str.upper()

    frc_df['contract_expiration_date'] = \
        clean_pudl.fix_int_na(frc_df['contract_expiration_date'],
                              float_na=np.nan,
                              int_na=-1,
                              str_na='')
    # Convert the 3-4 digit (MYY|MMYY) date of contract expiration to
    # two fields MM and YYYY for easier analysis later.
    exp_month = frc_df.contract_expiration_date. \
        apply(lambda x: x[:-2] if x != '' else x)
    # This gets rid of some bad data that's not in (MYY|MMYY) format.
    exp_month = \
        exp_month.apply(lambda x: x if x != '' and int(x) <= 12 else '')
    exp_year = frc_df.contract_expiration_date. \
        apply(lambda x: '20' + x[-2:] if x != '' else x)

    frc_df['contract_expiration_date'] = \
        pd.to_datetime({'year': exp_year,
                        'month': exp_month,
                        'day': 1})

    frc_df['report_date'] = pd.to_datetime({'year': frc_df.year,
                                            'month': frc_df.month,
                                            'day': 1})
    frc_df.drop(['year', 'month'], axis=1, inplace=True)
    frc_df['coalmine_id'] = clean_pudl.fix_int_na(frc_df['coalmine_id'],
                                                  float_na=np.nan,
                                                  int_na=-1,
                                                  str_na='')
    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(frc_df, 'fuel_receipts_costs_eia923', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def ingest_stocks_eia923(pudl_engine, eia923_dfs, csvdir='', keep_csv=True):
    """Ingest data on fuel stocks from EIA Form 923."""
    pass

###############################################################################
###############################################################################
# BEGIN EIA860 INGEST FUNCTIONS
###############################################################################
###############################################################################


def ingest_boiler_generator_assn_eia860(pudl_engine, eia860_dfs,
                                        csvdir='', keep_csv=True):
    """
    Ingest data on individual generators from EIA Form 860.

    Populates the boiler_generator_assn_eia860 table.

    Args:
        pudl_engine (sqlalchemy.engine): a connection to the PUDL DB.
        eia860_dfs (dictionary of pandas.DataFrame): Each entry in this
            dictionary of DataFrame objects corresponds to a page from the
            EIA860 form, as reported in the Excel spreadsheets they distribute.
        csvdir (string): Path to the directory where the CSV files representing
            our data tables should be written, before being read in to the
            postgres database directly.
        keep_csv (boolean): If True, do not delete the CSV files after they
            have been read into the database. If False, remove them.

    Returns: Nothing.
    """
    # Populating the 'generators_eia923' table
    b_g_df = eia860_dfs['boiler_generator_assn'].copy()

    b_g_df.rename(columns={'utility_id': 'operator_id',
                           'plant_code': 'plant_id'},
                  inplace=True)

    b_g_cols = ['operator_id',
                'plant_id',
                'boiler_id',
                'generator_id']

    b_g_df = b_g_df[b_g_cols]

    # We need to cast the generator_id column as type str because sometimes
    # it is heterogeneous int/str which make drop_duplicates fail.
    b_g_df['generator_id'] = b_g_df['generator_id'].astype(str)
    b_g_df = b_g_df.drop_duplicates().dropna()
    b_g_df['plant_id'] = b_g_df['plant_id'].astype(int)

    # Write the dataframe out to a csv file and load it directly
    csv_dump_load(b_g_df, 'boiler_generator_assn_eia860', pudl_engine,
                  csvdir=csvdir, keep_csv=keep_csv)


def create_dfs_eia860(files=pc.files_eia860,
                      eia860_years=pc.eia860_working_years,
                      verbose=True):
    """
    Creates a dictionary of pages (keys) to dataframes (values) from eia860
    tabs.

    Args:
        a list of eia860 files
        a list of years

    Returns:
        dictionary of pages (key) to dataframes (values)

    """
    # Prep for ingesting EIA860
    # Create excel objects
    eia860_dfs = {}
    for file in files:
        eia860_xlsx = eia860.get_eia860_xlsx(
            eia860_years, pc.files_dict_eia860[file])
        # Create DataFrames
        pages = pc.file_pages_eia860[file]

        for page in pages:
            eia860_dfs[page] = eia860.get_eia860_page(page, eia860_xlsx,
                                                      years=eia860_years,
                                                      verbose=verbose)
    return(eia860_dfs)

###############################################################################
###############################################################################
# BEGIN DATABASE INITIALIZATION
###############################################################################
###############################################################################


def init_db(ferc1_tables=pc.ferc1_pudl_tables,
            ferc1_years=range(2007, 2016),
            eia923_tables=pc.eia923_pudl_tables,
            eia923_years=range(2011, 2016),
            eia860_tables=pc.eia860_pudl_tables,
            eia860_years=pc.eia860_working_years,
            verbose=True, debug=False, testing=False,
            csvdir=os.path.join(settings.PUDL_DIR, 'results', 'csvdump'),
            keep_csv=True):
    """
    Create the PUDL database and fill it up with data.

    Args:
        ferc1_tables (list): The list of tables that will be created and
            ingested. By default only known to be working tables are ingested.
            That list of tables is defined in pudl.constants.
        ferc1_years (list): The list of years from which to pull FERC Form 1
            data.
        eia923_tables (list): The list of tables that will be created and
            ingested. By default only known to be working tables are ingested.
            That list of tables is defined in pudl.constants.
        eia923_years (list): The list of years from which to pull EIA 923
            data.
        debug (bool): You can tell init_db to ingest whatever list of tables
            you want, but if your desired table is not in the list of known to
            be working tables, you need to set debug=True (otherwise init_db
            won't let you).
    """
    # Make sure that the tables we're being asked to ingest can actually be
    # pulled into both the FERC Form 1 DB, and the PUDL DB...
    if not debug:
        for table in ferc1_tables:
            assert(table in pc.ferc1_working_tables)
            assert(table in pc.ferc1_pudl_tables)

    if not debug:
        for table in eia923_tables:
            assert(table in pc.eia923_pudl_tables)

    # Connect to the PUDL DB, wipe out & re-create tables:
    pudl_engine = db_connect_pudl(testing=testing)
    drop_tables_pudl(pudl_engine)
    create_tables_pudl(pudl_engine)
    # Populate all the static tables:
    if verbose:
        print("Ingesting static PUDL tables...")
    ingest_static_tables(pudl_engine)
    # Populate tables that relate FERC1 & EIA923 data to each other.
    if verbose:
        print("Sniffing EIA923/FERC1 glue tables...")
    ingest_glue_tables(pudl_engine)

    # BEGIN INGESTING FERC FORM 1 DATA:
    ferc1_ingest_functions = {
        'f1_fuel': ingest_fuel_ferc1,
        'f1_steam': ingest_plants_steam_ferc1,
        'f1_gnrt_plant': ingest_plants_small_ferc1,
        'f1_hydro': ingest_plants_hydro_ferc1,
        'f1_pumped_storage': ingest_plants_pumped_storage_ferc1,
        'f1_plant_in_srvce': ingest_plant_in_service_ferc1,
        'f1_purchased_pwr': ingest_purchased_power_ferc1,
        'f1_accumdepr_prvsn': ingest_accumulated_depreciation_ferc1}

    ferc1_engine = ferc1.db_connect_ferc1(testing=testing)
    for table in ferc1_ingest_functions.keys():
        if table in ferc1_tables:
            if verbose:
                print("Ingesting {} from FERC Form 1 into PUDL.".format(table))
            ferc1_ingest_functions[table](pudl_engine,
                                          ferc1_engine,
                                          ferc1_years)

    # Prep for ingesting EIA923
    # Create excel objects
    eia923_xlsx = eia923.get_eia923_xlsx(eia923_years)

    # Create DataFrames
    eia923_dfs = {}
    for page in pc.tab_map_eia923.columns:
        if (page == 'plant_frame'):
            eia923_dfs[page] = eia923.get_eia923_plant_info(
                eia923_years, eia923_xlsx)
        else:
            eia923_dfs[page] = eia923.get_eia923_page(page, eia923_xlsx,
                                                      years=eia923_years,
                                                      verbose=verbose)

    # NOW START INGESTING EIA923 DATA:
    eia923_ingest_functions = {
        'plant_info_eia923': ingest_plant_info_eia923,
        'generation_fuel_eia923': ingest_generation_fuel_eia923,
        # 'plant_ownership_eia923': ingest_plant_ownership_eia923,
        'boilers_eia923': ingest_boilers_eia923,
        'boiler_fuel_eia923': ingest_boiler_fuel_eia923,
        'generation_eia923': ingest_generation_eia923,
        'generators_eia923': ingest_generators_eia923,
        'coalmine_info_eia923': ingest_coalmine_info_eia923,
        'fuel_receipts_costs_eia923': ingest_fuel_receipts_costs_eia923,
    }

    for table in eia923_ingest_functions.keys():
        if table in eia923_tables:
            if verbose:
                print("Ingesting {} from EIA 923 into PUDL.".format(table))
            eia923_ingest_functions[table](pudl_engine, eia923_dfs,
                                           csvdir=csvdir, keep_csv=keep_csv)

    eia860_dfs = create_dfs_eia860(files=pc.files_eia860,
                                   eia860_years=eia860_years, verbose=verbose)

    eia860_ingest_functions = {
        'boiler_generator_assn_eia860': ingest_boiler_generator_assn_eia860}

    for table in eia860_ingest_functions.keys():
        if table in eia860_tables:
            if verbose:
                print("Ingesting {} from EIA 860 into PUDL.".format(table))
            eia860_ingest_functions[table](pudl_engine, eia860_dfs,
                                           csvdir=csvdir, keep_csv=keep_csv)
