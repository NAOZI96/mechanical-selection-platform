from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.modules.engineering_common import ResultClassification
from app.modules.gear_drive import GearDriveInput
from app.modules.gear_drive import calculate as calculate_gear
from app.modules.lead_screw import LeadScrewInput
from app.modules.lead_screw import calculate as calculate_lead_screw
from app.modules.shaft_bearing import ShaftBearingInput
from app.modules.shaft_bearing import calculate as calculate_shaft_bearing
from app.modules.transmission_check import (
    TransmissionCheckInput,
)
from app.modules.transmission_check import (
    calculate as calculate_transmission,
)


def transmission_values(*, include_candidate: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": "user_input",
        "basis_reference": "独立金样 TC-A-001",
        "input_speed_rpm": 1500.0,
        "input_torque_nm": 100.0,
        "stages": (
            {
                "stage_name": "一级",
                "ratio": 3.0,
                "efficiency": 0.95,
                "ratio_source_status": "user_input",
                "ratio_reference": "TC-A-001 齿数商",
                "efficiency_source_status": "user_input",
                "efficiency_reference": "TC-A-001 审核效率",
            },
            {
                "stage_name": "二级",
                "ratio": 4.0,
                "efficiency": 0.9,
                "ratio_source_status": "user_input",
                "ratio_reference": "TC-A-001 齿数商",
                "efficiency_source_status": "user_input",
                "efficiency_reference": "TC-A-001 审核效率",
            },
        ),
    }
    if include_candidate:
        values.update(
            {
                "candidate_rated_output_torque_nm": 1100.0,
                "candidate_source_status": "manufacturer_data",
                "candidate_reference": "TC-A-001 候选样本",
            }
        )
    return values


def gear_values(*, include_candidates: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": "user_input",
        "basis_reference": "独立金样 GD-A-001",
        "module_mm": 4.0,
        "pinion_teeth": 20,
        "gear_teeth": 60,
        "pressure_angle_deg": 20.0,
        "input_speed_rpm": 1200.0,
        "input_torque_nm": 100.0,
        "mesh_efficiency": 0.97,
    }
    if include_candidates:
        values.update(
            {
                "allowable_tangential_force_n": 3000.0,
                "allowable_tangential_force_source_status": "manufacturer_data",
                "allowable_tangential_force_reference": "GD-A-001 候选样本",
                "maximum_pitch_line_speed_m_s": 8.0,
                "maximum_pitch_line_speed_source_status": "manufacturer_data",
                "maximum_pitch_line_speed_reference": "GD-A-001 候选样本",
            }
        )
    return values


def shaft_bearing_values(*, include_candidate: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": "user_input",
        "basis_reference": "独立金样 SB-A-001",
        "bearing_radial_load_n": 5000.0,
        "bearing_axial_load_n": 1000.0,
        "bearing_speed_rpm": 600.0,
        "basic_dynamic_load_rating_n": 44000.0,
        "dynamic_rating_source_status": "manufacturer_data",
        "dynamic_rating_reference": "SB-A-001 轴承样本",
        "radial_factor_x": 0.56,
        "radial_factor_x_source_status": "standard_confirmed",
        "radial_factor_x_reference": "SB-A-001 审核表 X",
        "axial_factor_y": 1.6,
        "axial_factor_y_source_status": "standard_confirmed",
        "axial_factor_y_reference": "SB-A-001 审核表 Y",
        "life_exponent_p": 3.0,
        "life_exponent_source_status": "standard_confirmed",
        "life_exponent_reference": "SB-A-001 球轴承寿命指数",
        "shaft_diameter_mm": 50.0,
        "shaft_bending_moment_nm": 500.0,
        "shaft_torque_nm": 300.0,
    }
    if include_candidate:
        values.update(
            {
                "allowable_von_mises_stress_mpa": 120.0,
                "allowable_stress_source_status": "project_setting",
                "allowable_stress_reference": "SB-A-001 已批准材料许用值",
            }
        )
    return values


def lead_screw_values(*, include_candidate: bool = True) -> dict[str, object]:
    values: dict[str, object] = {
        "basis_source_status": "user_input",
        "basis_reference": "独立金样 LS-A-001",
        "axial_force_n": 10000.0,
        "mean_thread_diameter_mm": 30.0,
        "root_diameter_mm": 24.0,
        "lead_mm_per_revolution": 6.0,
        "friction_coefficient": 0.12,
        "friction_source_status": "user_input",
        "friction_reference": "LS-A-001 审核摩擦值",
        "rotational_speed_rpm": 300.0,
        "youngs_modulus_gpa": 210.0,
        "youngs_modulus_source_status": "standard_confirmed",
        "youngs_modulus_reference": "LS-A-001 材料数据",
        "unsupported_length_mm": 600.0,
        "effective_length_factor": 1.0,
        "effective_length_factor_source_status": "project_setting",
        "effective_length_factor_reference": "LS-A-001 两端铰支模型",
    }
    if include_candidate:
        values.update(
            {
                "candidate_allowable_axial_load_n": 15000.0,
                "candidate_source_status": "manufacturer_data",
                "candidate_reference": "LS-A-001 候选样本",
            }
        )
    return values


class TransmissionCheckTests(unittest.TestCase):
    def test_two_stage_independent_gold_case(self) -> None:
        result = calculate_transmission(TransmissionCheckInput(**transmission_values()))

        # 独立算术：i=3*4=12；eta=.95*.90=.855；T2=100*12*.855=1026 N*m；
        # omega2=(1500*2*pi/60)/12=13.089969389957473 rad/s；
        # P2=1026*13.089969389957473=13430.308594096367 W。
        self.assertAlmostEqual(float(result.total_ratio.value), 12.0, places=12)
        self.assertAlmostEqual(float(result.total_efficiency.value), 0.855, places=12)
        self.assertAlmostEqual(float(result.output_torque_nm.value), 1026.0, places=12)
        self.assertAlmostEqual(
            float(result.output_speed_rad_s.value),
            13.089969389957473,
            places=12,
        )
        self.assertAlmostEqual(
            float(result.output_power_w.value),
            13430.308594096367,
            places=9,
        )
        self.assertEqual(result.candidate_torque_satisfied.value, True)
        self.assertAlmostEqual(float(result.candidate_torque_margin_nm.value), 74.0, places=12)
        self.assertEqual(result.candidate_torque_margin_nm.formula_ids, ("CHECK-003",))
        self.assertEqual(len(result.stage_results), 2)

    def test_four_stage_path_executes_all_dynamic_stage_formula_ids(self) -> None:
        values = transmission_values(include_candidate=False)
        values["stages"] = (
            *values["stages"],
            {
                "stage_name": "三级",
                "ratio": 2.0,
                "efficiency": 0.98,
                "ratio_source_status": "user_input",
                "ratio_reference": "TC-A-004 齿数商",
                "efficiency_source_status": "user_input",
                "efficiency_reference": "TC-A-004 审核效率",
            },
            {
                "stage_name": "四级",
                "ratio": 5.0,
                "efficiency": 0.97,
                "ratio_source_status": "user_input",
                "ratio_reference": "TC-A-004 齿数商",
                "efficiency_source_status": "user_input",
                "efficiency_reference": "TC-A-004 审核效率",
            },
        )
        result = calculate_transmission(TransmissionCheckInput(**values))

        # 独立算术：i=3*4*2*5=120；eta=.95*.90*.98*.97=.812763；
        # T_out=100*120*.812763=9753.156 N*m。
        self.assertAlmostEqual(float(result.total_ratio.value), 120.0, places=12)
        self.assertAlmostEqual(float(result.total_efficiency.value), 0.812763, places=12)
        self.assertAlmostEqual(float(result.output_torque_nm.value), 9753.156, places=9)
        self.assertEqual(len(result.stage_results), 4)
        formula_ids = {step.formula_id for step in result.calculation_steps}
        self.assertTrue(
            {
                "KIN-013",
                "TORQUE-013",
                "POWER-013",
                "KIN-014",
                "TORQUE-014",
                "POWER-014",
            }.issubset(formula_ids)
        )

    def test_stage_count_and_cross_field_boundaries(self) -> None:
        single_stage_values = transmission_values(include_candidate=False)
        single_stage_values["stages"] = (single_stage_values["stages"][0],)
        single_stage_result = calculate_transmission(TransmissionCheckInput(**single_stage_values))
        self.assertEqual(len(single_stage_result.stage_results), 1)
        self.assertAlmostEqual(float(single_stage_result.total_ratio.value), 3.0, places=12)

        five_stages = list(transmission_values()["stages"])
        five_stages.extend((five_stages[0], five_stages[1], five_stages[0]))
        with self.assertRaises(ValidationError):
            TransmissionCheckInput(**{**transmission_values(), "stages": tuple(five_stages)})

        duplicated = list(transmission_values()["stages"])
        duplicated[1] = {**duplicated[1], "stage_name": "一级"}
        with self.assertRaises(ValidationError):
            TransmissionCheckInput(**{**transmission_values(), "stages": tuple(duplicated)})

        partial_candidate = transmission_values(include_candidate=False)
        partial_candidate["candidate_rated_output_torque_nm"] = 1100.0
        with self.assertRaises(ValidationError):
            TransmissionCheckInput(**partial_candidate)

    def test_missing_candidate_is_review_required(self) -> None:
        result = calculate_transmission(TransmissionCheckInput(**transmission_values(include_candidate=False)))
        self.assertIsNone(result.candidate_torque_utilization.value)
        self.assertIs(
            result.candidate_torque_utilization.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIs(
            result.candidate_torque_satisfied.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIn("CANDIDATE_TORQUE_MISSING", {warning.code for warning in result.warnings})

    def test_repeat_execution_is_identical(self) -> None:
        source = TransmissionCheckInput(**transmission_values())
        self.assertEqual(
            calculate_transmission(source).model_dump(mode="json"),
            calculate_transmission(source).model_dump(mode="json"),
        )


class GearDriveTests(unittest.TestCase):
    def test_spur_gear_independent_gold_case(self) -> None:
        result = calculate_gear(GearDriveInput(**gear_values()))

        # 独立算术：m=.004 m，d1=.004*20=.08 m，d2=.004*60=.24 m，a=.16 m；
        # i=60/20=3，Ft=2*100/.08=2500 N，Fr=2500*tan(20 deg)=909.9255856655059 N；
        # v=(1200*2*pi/60)*.08/2=5.026548245743669 m/s，T2=100*3*.97=291 N*m。
        self.assertAlmostEqual(float(result.pinion_pitch_diameter_m.value), 0.08, places=12)
        self.assertAlmostEqual(float(result.gear_pitch_diameter_m.value), 0.24, places=12)
        self.assertAlmostEqual(float(result.center_distance_m.value), 0.16, places=12)
        self.assertAlmostEqual(float(result.transmission_ratio.value), 3.0, places=12)
        self.assertAlmostEqual(float(result.tangential_force_n.value), 2500.0, places=9)
        self.assertAlmostEqual(
            float(result.radial_force_n.value),
            909.9255856655059,
            places=9,
        )
        self.assertAlmostEqual(
            float(result.pitch_line_speed_m_s.value),
            5.026548245743669,
            places=12,
        )
        self.assertAlmostEqual(float(result.output_torque_nm.value), 291.0, places=12)
        self.assertEqual(result.tangential_force_satisfied.value, True)
        self.assertIn("tooth_root_bending_strength", result.unchecked_items)
        self.assertIn("GEAR_STRENGTH_NOT_CHECKED", {warning.code for warning in result.warnings})

    def test_angle_and_optional_supplier_data_boundaries(self) -> None:
        with self.assertRaises(ValidationError):
            GearDriveInput(**{**gear_values(), "pressure_angle_deg": 90.0})

        partial_force = gear_values(include_candidates=False)
        partial_force["allowable_tangential_force_n"] = 3000.0
        with self.assertRaises(ValidationError):
            GearDriveInput(**partial_force)

        with self.assertRaises(ValidationError):
            GearDriveInput(**{**gear_values(), "basis_reference": "   "})

    def test_missing_supplier_limits_are_review_required(self) -> None:
        result = calculate_gear(GearDriveInput(**gear_values(include_candidates=False)))
        for item in (
            result.tangential_force_utilization,
            result.tangential_force_satisfied,
            result.pitch_line_speed_utilization,
            result.pitch_line_speed_satisfied,
        ):
            self.assertIsNone(item.value)
            self.assertIs(item.classification, ResultClassification.REVIEW_REQUIRED)

    def test_repeat_execution_is_identical(self) -> None:
        source = GearDriveInput(**gear_values())
        self.assertEqual(
            calculate_gear(source).model_dump(mode="json"),
            calculate_gear(source).model_dump(mode="json"),
        )


class ShaftBearingTests(unittest.TestCase):
    def test_bearing_life_and_shaft_stress_independent_gold_case(self) -> None:
        result = calculate_shaft_bearing(ShaftBearingInput(**shaft_bearing_values()))

        # 独立算术：P=.56*5000+1.6*1000=4400 N；
        # L10=(44000/4400)^3=1000 (百万转)，L10h=1000e6/(60*600)=27777.777777777777 h。
        # d=.05 m，sigma=32*500/(pi*.05^3)=40743665.4315252 Pa；
        # tau=16*300/(pi*.05^3)=12223099.62945756 Pa；
        # sigma_vm=sqrt(sigma^2+3*tau^2)=45915779.05743295 Pa。
        self.assertAlmostEqual(float(result.equivalent_dynamic_load_n.value), 4400.0, places=9)
        self.assertAlmostEqual(
            float(result.bearing_l10_million_revolutions.value),
            1000.0,
            places=9,
        )
        self.assertAlmostEqual(
            float(result.bearing_l10_life_hours.value),
            27777.777777777777,
            places=9,
        )
        self.assertAlmostEqual(
            float(result.shaft_bending_stress_pa.value),
            40743665.4315252,
            places=5,
        )
        self.assertAlmostEqual(
            float(result.shaft_torsional_shear_stress_pa.value),
            12223099.62945756,
            places=5,
        )
        self.assertAlmostEqual(
            float(result.shaft_von_mises_stress_pa.value),
            45915779.05743295,
            places=5,
        )
        self.assertEqual(result.allowable_stress_satisfied.value, True)
        self.assertAlmostEqual(
            float(result.allowable_stress_margin_pa.value),
            74084220.94256705,
            places=5,
        )
        self.assertEqual(result.allowable_stress_margin_pa.formula_ids, ("CHECK-003",))

    def test_cross_field_and_source_requirements(self) -> None:
        with self.assertRaises(ValidationError):
            ShaftBearingInput(**{**shaft_bearing_values(), "bearing_speed_rpm": 0.0})
        with self.assertRaises(ValidationError):
            ShaftBearingInput(
                **{
                    **shaft_bearing_values(),
                    "bearing_radial_load_n": 0.0,
                    "bearing_axial_load_n": 0.0,
                }
            )
        with self.assertRaises(ValidationError):
            ShaftBearingInput(
                **{
                    **shaft_bearing_values(),
                    "shaft_bending_moment_nm": 0.0,
                    "shaft_torque_nm": 0.0,
                }
            )
        missing_x_source = shaft_bearing_values()
        del missing_x_source["radial_factor_x_reference"]
        with self.assertRaises(ValidationError):
            ShaftBearingInput(**missing_x_source)

        partial_allowable = shaft_bearing_values(include_candidate=False)
        partial_allowable["allowable_von_mises_stress_mpa"] = 120.0
        with self.assertRaises(ValidationError):
            ShaftBearingInput(**partial_allowable)

    def test_missing_allowable_stress_is_review_required(self) -> None:
        result = calculate_shaft_bearing(ShaftBearingInput(**shaft_bearing_values(include_candidate=False)))
        self.assertIsNone(result.allowable_stress_utilization.value)
        self.assertIs(
            result.allowable_stress_utilization.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIs(
            result.allowable_stress_satisfied.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIn("ALLOWABLE_STRESS_MISSING", {warning.code for warning in result.warnings})

    def test_repeat_execution_is_identical(self) -> None:
        source = ShaftBearingInput(**shaft_bearing_values())
        self.assertEqual(
            calculate_shaft_bearing(source).model_dump(mode="json"),
            calculate_shaft_bearing(source).model_dump(mode="json"),
        )


class LeadScrewTests(unittest.TestCase):
    def test_square_thread_and_euler_independent_gold_case(self) -> None:
        result = calculate_lead_screw(LeadScrewInput(**lead_screw_values()))

        # 独立算术：tan(lambda)=.006/(pi*.03)=.06366197723675814；
        # lambda=.06357618167828312 rad；
        # T_up=10000*.03/2*(tan(lambda)+.12)/(1-.12*tan(lambda))
        #     =27.761377890392023 N*m；
        # T_down=10000*.03/2*(.12-tan(lambda))/(1+.12*tan(lambda))
        #       =8.386634248253639 N*m；
        # eta=10000*.006/(2*pi*T_up)=.34397776015356396；v=.006*300/60=.03 m/s。
        # I=pi*.024^4/64=1.628601631620949e-8 m4；
        # Fcr=pi^2*210e9*I/(1*.6)^2=93762.98068122665 N。
        self.assertAlmostEqual(float(result.lead_angle_rad.value), 0.06357618167828312, places=12)
        self.assertAlmostEqual(
            float(result.raising_torque_nm.value),
            27.761377890392023,
            places=12,
        )
        self.assertAlmostEqual(
            float(result.lowering_torque_nm.value),
            8.386634248253639,
            places=12,
        )
        self.assertAlmostEqual(
            float(result.raising_efficiency.value),
            0.34397776015356396,
            places=12,
        )
        self.assertAlmostEqual(float(result.linear_speed_m_s.value), 0.03, places=12)
        self.assertEqual(result.self_locking.value, True)
        self.assertAlmostEqual(
            float(result.euler_critical_load_n.value),
            93762.98068122665,
            places=7,
        )
        self.assertEqual(result.euler_buckling_satisfied.value, True)
        self.assertEqual(result.candidate_axial_load_satisfied.value, True)
        self.assertAlmostEqual(float(result.candidate_axial_load_margin_n.value), 5000.0, places=12)
        self.assertEqual(result.candidate_axial_load_margin_n.formula_ids, ("CHECK-006",))

    def test_geometry_formula_and_candidate_cross_field_boundaries(self) -> None:
        with self.assertRaises(ValidationError):
            LeadScrewInput(
                **{
                    **lead_screw_values(),
                    "root_diameter_mm": 30.0,
                }
            )
        with self.assertRaises(ValidationError):
            LeadScrewInput(
                **{
                    **lead_screw_values(),
                    "friction_coefficient": 16.0,
                }
            )
        partial_candidate = lead_screw_values(include_candidate=False)
        partial_candidate["candidate_allowable_axial_load_n"] = 15000.0
        with self.assertRaises(ValidationError):
            LeadScrewInput(**partial_candidate)

    def test_missing_candidate_is_review_required(self) -> None:
        result = calculate_lead_screw(LeadScrewInput(**lead_screw_values(include_candidate=False)))
        self.assertIsNone(result.candidate_axial_load_utilization.value)
        self.assertIs(
            result.candidate_axial_load_utilization.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIs(
            result.candidate_axial_load_satisfied.classification,
            ResultClassification.REVIEW_REQUIRED,
        )
        self.assertIn(
            "CANDIDATE_AXIAL_LOAD_MISSING",
            {warning.code for warning in result.warnings},
        )

    def test_repeat_execution_is_identical(self) -> None:
        source = LeadScrewInput(**lead_screw_values())
        self.assertEqual(
            calculate_lead_screw(source).model_dump(mode="json"),
            calculate_lead_screw(source).model_dump(mode="json"),
        )


if __name__ == "__main__":
    unittest.main()
