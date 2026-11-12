
from decimal import Decimal, ROUND_HALF_UP


class ReverseLogisticsService:

    @staticmethod
    def evaluate_inspection(cosmetic: int, functional: int):
        composite = (cosmetic * 0.4) + (functional * 0.6)

        if composite >= 8.5:
            return "A", "good", "restock"
        elif composite >= 6.5:
            return "B", "good", "restock"
        elif composite >= 4.0:
            return "C", "damaged", "refurbish"
        else:
            return "F", "unusable", "scrap"

    @staticmethod
    def calculate_deposit_settlement(initial_deposit, grade):
        deposit = Decimal(str(initial_deposit or 0)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        if deposit <= 0:
            return (
                None,
                Decimal("0.00"),
                "No security deposit was held."
            )

        if grade == "A":
            return (
                "refund",
                deposit,
                "Grade A: Full security deposit refunded."
            )

        elif grade == "B":
            refund = (deposit * Decimal("0.90")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
            deduction = deposit - refund

            return (
                "refund",
                refund,
                f"Grade B: 10% cleaning fee deducted: {deduction}."
            )

        elif grade == "C":
            refund = (deposit * Decimal("0.50")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )
            deduction = deposit - refund

            return (
                "refund",
                refund,
                f"Grade C: 50% refurbishment deduction: {deduction}."
            )

        else:
            return (
                "adjustment",
                deposit,
                "Grade F: Deposit forfeited due to total asset loss."
            )
