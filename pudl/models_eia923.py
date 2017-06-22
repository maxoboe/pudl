"""Database models for PUDL tables derived from EIA Form 923 Data."""

from sqlalchemy import Boolean, Integer, String, Float, Numeric, Date
from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
import models

###########################################################################
# EIA Form 923 tables which represent constants or metadata
# (e.g. fuel types and fuel units)
###########################################################################


class CoalMineInfoEIA923(models.PUDLBase):
    """Information pertaining to individual coal mines listed in EIA 923."""

    __tablename__ = 'coalmine_info_eia923'
    id = Column(Integer, autoincrement=True, primary_key=True)  # surrogate key
    coalmine_name = Column(String)
    coalmine_type = Column(String, ForeignKey('coalmine_type_eia923.abbr'))
    coalmine_state = Column(String, ForeignKey('coalmine_state_eia923.abbr'))
    # TODO check feasibility t add FK/constants or map to FIPS code used by EIA
    coalmine_county = Column(Integer)
    # TODO check feasibility to add FK/constants or map to MSHA ID# used by EIA
    coalmine_msha_id = Column(Integer)


class BoilersEIA923(models.PUDLBase):
    """List of Boiler IDs specific to each plant in EIA Form 923 Page 3."""

    __tablename__ = 'boilers_eia923'
    plant_id = Column(Integer, ForeignKey('plants_eia923.plant_id'),
                      primary_key=True)
    boiler_id = Column(String, primary_key=True)
    prime_mover = Column(String,
                         ForeignKey('prime_movers_eia923.abbr'),
                         nullable=False)


class GeneratorEIA923(models.PUDLBase):
    """List of Generator IDs specific to each plant in EIA Form 923 Page 4."""

    __tablename__ = 'generators_eia923'
    plant_id = Column(Integer, ForeignKey('plants_eia923.plant_id'),
                      primary_key=True)
    generator_id = Column(String, primary_key=True)
    prime_mover = Column(String,
                         ForeignKey('prime_movers_eia923.abbr'),
                         nullable=False)


class FuelUnitEIA923(models.PUDLBase):
    """Static list of physical unit labels used by EIA in Form 923."""

    __tablename__ = 'fuel_units_eia923'
    abbr = Column(String, primary_key=True)
    unit = Column(String)


class FuelTypeEIA923(models.PUDLBase):
    """
    Static list of fuel types used by EIA in Form 923.

    Enumerated on Page 7 of EIA Form 923.
    """

    __tablename__ = 'fuel_type_eia923'
    abbr = Column(String, primary_key=True)
    fuel_type = Column(String, nullable=False)
    fuel_unit = Column(String, ForeignKey('fuel_units_eia923.abbr'))


class FuelGroupEIA923(models.PUDLBase):
    """Grouping of energy sources into fuel groups, used in EIA Form 923."""

    __tablename__ = 'fuel_group_eia923'
    group = Column(String, primary_key=True)


class RespondentFrequencyEIA923(models.PUDLBase):
    """
    Plant reporting frequency in EIA Form 923.

    Used by EIA in Form 923, Page 5: Fuel Receipts and Costs
    """

    __tablename__ = 'respondent_frequency_eia923'
    abbr = Column(String, primary_key=True)
    unit = Column(String, nullable=False)


class ContractTypeEIA923(models.PUDLBase):
    """Type of contract under which fuel receipt occured."""

    __tablename__ = 'contract_type_eia923'
    abbr = Column(String, primary_key=True)
    contract_type = Column(String, nullable=False)


class SectorEIA(models.PUDLBase):
    """EIA's internal consolidated NAICS sectors."""

    __tablename__ = 'sector_eia'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class FuelTypeAER(models.PUDLBase):
    """Static list of fuel types using AER codes, reported in EIA Form 923."""

    __tablename__ = 'fuel_type_aer_eia923'
    abbr = Column(String, primary_key=True)
    fuel_type = Column(String, nullable=False)


class PrimeMoverEIA923(models.PUDLBase):
    """Static list of prime movers used by EIA in Form 923."""

    __tablename__ = 'prime_movers_eia923'
    abbr = Column(String, primary_key=True)
    prime_mover = Column(String, nullable=False)


class EnergySourceEIA923(models.PUDLBase):
    """Fuel code associated with fuel receipts in EIA Form 923."""

    __tablename__ = 'energy_source_eia923'
    abbr = Column(String, primary_key=True)
    source = Column(String, nullable=False)


class CoalMineTypeEIA923(models.PUDLBase):
    """Type of coal mine, as used in EIA Form 923."""

    __tablename__ = 'coalmine_type_eia923'
    abbr = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class CoalMineStateEIA923(models.PUDLBase):
    """State and country abbreviations for coal mine locations."""

    __tablename__ = 'coalmine_state_eia923'
    abbr = Column(String, primary_key=True)
    state = Column(String, nullable=False)


class NaturalGasTransportEIA923(models.PUDLBase):
    """Contract type for natural gas capacity service."""

    __tablename__ = 'natural_gas_transport_eia923'
    abbr = Column(String, primary_key=True)
    status = Column(String, nullable=False)


class TransportModeEIA923(models.PUDLBase):
    """Mode used for longest & 2nd longest distance in EIA Form 923."""

    __tablename__ = 'transport_modes_eia923'
    abbr = Column(String, primary_key=True)
    mode = Column(String, nullable=False)


class AERFuelCategoryEIA923(models.PUDLBase):
    """PUDL Consolidation of AER Fuel Types."""

    __tablename__ = 'aer_fuel_type_strings'
    name = Column(String, primary_key=True)


###########################################################################
# Tables which represent EIA Form 923 data. E.g. Fuel Receipts.
###########################################################################


class PlantOwnershipEIA923(models.PUDLBase):
    """
    Information describing which entities own & operate power plants.

    For now this table only describes how the reporting operator of a plant_id
    changes from year to year, but it may also be used to house data from the
    EIA860 form, describing ownership shares of various plants, year by year.
    """

    __tablename__ = 'plant_ownership_eia923'
    plant_id = Column(Integer, primary_key=True)
    year = Column(Integer, primary_key=True)
    operator_id = Column(Integer, ForeignKey('utilities_eia923.operator_id'))


class OperatorInfoEIA923(models.PUDLBase):
    """
    Information specific to plant operators (typically utilities).

    Reported on Page 1 of EIA Form 923.
    """

    __tablename__ = 'operator_info_eia923'
    operator_id = Column(Integer,
                         ForeignKey('utilities_eia923.operator_id'),
                         primary_key=True)
    regulated = Column(Boolean, primary_key=True)


class PlantInfoEIA923(models.PUDLBase):
    """Information specific to individual power plants.

    Reported on Page 1 of EIA Form 923.
    """

    __tablename__ = 'plant_info_eia923'
    # TODO: This should be a FK pointing at plants_eia923.plant_id_eia923
    plant_id = Column(Integer, primary_key=True)
    combined_heat_power = Column(Boolean)
    plant_state = Column(String, ForeignKey('us_states.abbr'))
    eia_sector = Column(Integer, ForeignKey('sector_eia.id'))
    naics_code = Column(Integer)
    reporting_frequency = \
        Column(String, ForeignKey('respondent_frequency_eia923.abbr'))
    # Census region & NERC region are nullable, because they're set from info
    # listed in the generation_fuel page of EIA923, which does not list the
    # entire universe of plants (those listed only in plant_frame will not have
    # these values set)
    census_region = Column(String, ForeignKey('census_regions.abbr'))
    nerc_region = Column(String, ForeignKey('nerc_region.abbr'))
    nameplate_capacity_mw = Column(Float)


class GenerationFuelEIA923(models.PUDLBase):
    """
    Monthly fuel consumption and electricity generation by plant.

    Reported on Page 1 of EIA Form 923.
    """

    __tablename__ = 'generation_fuel_eia923'

    id = Column(Integer, autoincrement=True, primary_key=True)  # surrogate key
    plant_id = Column(Integer,
                      ForeignKey('plants_eia923.plant_id'),
                      nullable=False)
    report_date = Column(Date, nullable=False)
    # TODO: Should nuclear_unit_id really be here? It's kind of part of the
    # plant_id... but also unit_id.  Seems weird but necessary to uniquely
    # identify the records as reported.
    nuclear_unit_id = Column(Integer)
    fuel_type = Column(String,
                       ForeignKey('fuel_type_eia923.abbr'),
                       nullable=False)
    aer_fuel_type = Column(String, ForeignKey('fuel_type_aer_eia923.abbr'))
    aer_fuel_category = Column(
        String, ForeignKey('aer_fuel_type_strings.name'))
    prime_mover = Column(String,
                         ForeignKey('prime_movers_eia923.abbr'),
                         nullable=False)
    fuel_consumed_total = Column(Float)
    fuel_consumed_for_electricity = Column(Float)
    fuel_mmbtu_per_unit = Column(Float)
    fuel_consumed_total_mmbtu = Column(Float)
    fuel_consumed_for_electricity_mmbtu = Column(Float)
    net_generation_mwh = Column(Float)


class BoilerFuelEIA923(models.PUDLBase):
    """Monthly fuel consumption by boiler reported on Page 3 of EIA 923."""

    __tablename__ = 'boiler_fuel_eia923'

    # Each month, for each unique combination of boiler id and prime mover and
    # fuel, there is one report for each boiler unit in each plant.
    # Primary key fields used previously:
    # plant, boiler, prime mover, fuel type, and year.

    id = Column(Integer, autoincrement=True, primary_key=True)  # surrogate key
    plant_id = Column(Integer, ForeignKey(
        'plants_eia923.plant_id'), nullable=False)
    boiler_id = Column(String, nullable=False)
    prime_mover = Column(String, ForeignKey('prime_movers_eia923.abbr'),
                         nullable=False)
    fuel_type = Column(String, ForeignKey('fuel_type_eia923.abbr'),
                       nullable=False)
    report_date = Column(Date, nullable=False)
    fuel_qty_consumed = Column(Float)
    fuel_mmbtu_per_unit = Column(Float)
    sulfur_content = Column(Float)
    ash_content = Column(Float)


class GenerationEIA923(models.PUDLBase):
    """Monthly electricity generation by generator from EIA923 Page 4."""

    __tablename__ = 'generation_eia923'

    # Each month, for each unique combination of generator id and prime mover
    # and fuel,there is one report for each generator unit in each plant.
    # Primary key fields used previously:
    # plant, generator, prime mover, year, and month.
    id = Column(Integer, autoincrement=True, primary_key=True)  # surrogate key
    plant_id = Column(Integer, ForeignKey('plants_eia923.plant_id'),
                      nullable=False)
    # TODO remove prime_mover since it's specific to generator_id?
    prime_mover = Column(String, ForeignKey('prime_movers_eia923.abbr'),
                         nullable=False)
    # TODO: Add FK constraint refering to (plant_id, generator_id) in the
    # generators_eia923 table.  Or at least give it a shot.
    generator_id = Column(String, nullable=False)
    report_date = Column(Date, nullable=False)
    net_generation_mwh = Column(Float)


class FuelReceiptsCostsEIA923(models.PUDLBase):
    """Fuel receipts & costs by plant &purchase from Page 5 of EIA Form 923."""

    __tablename__ = 'fuel_receipts_costs_eia923'

    # surrogate key
    fuel_receipt_id = Column(Integer, primary_key=True, autoincrement=True)
    plant_id = Column(Integer,
                      ForeignKey('plants_eia923.plant_id'),
                      nullable=False)
    report_date = Column(Date, nullable=False)
    contract_type = Column(String, ForeignKey('contract_type_eia923.abbr'))
    contract_expiration_date = Column(Date)
    energy_source = Column(String, ForeignKey('energy_source_eia923.abbr'))
    fuel_group = Column(String, ForeignKey('fuel_group_eia923.group'))
    coalmine_id = Column(Integer, ForeignKey('coalmine_info_eia923.id'))
    supplier = Column(String, nullable=False)  # TODO FK new table?
    fuel_quantity = Column(Float, nullable=False)
    average_heat_content = Column(Float, nullable=False)
    average_sulfur_content = Column(Float, nullable=False)
    average_ash_content = Column(Float, nullable=False)
    average_mercury_content = Column(Float)
    fuel_cost = Column(Float)
    primary_transportation_mode = Column(
        String,
        ForeignKey('transport_modes_eia923.abbr'))
    secondary_transportation_mode = Column(
        String,
        ForeignKey('transport_modes_eia923.abbr'))
    natural_gas_transport = Column(
        String,
        ForeignKey('natural_gas_transport_eia923.abbr'))
