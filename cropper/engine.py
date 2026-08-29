"""五步裁剪引擎总入口"""

from cropper.constraints import CustomerConstraints
from cropper.five_steps import FiveStepCropper
from cropper.plan_output import CropPlan


def crop_for_customer(constraints: CustomerConstraints) -> CropPlan:
    """为指定客户生成裁剪方案"""
    cropper = FiveStepCropper()
    plan_dict = cropper.execute(constraints)
    return CropPlan(
        customer_id=plan_dict["customer_id"],
        enabled_modules=plan_dict["enabled_modules"],
        deleted_modules=plan_dict["deleted_modules"],
        simplifications=plan_dict["simplifications"],
        automations=plan_dict["automations"],
        timeline_suggestion=plan_dict["timeline_suggestion"],
    )