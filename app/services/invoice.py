"""Hisob-faktura PDF generatori (reportlab)."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.order import Order


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def generate_invoice_pdf(order: Order, restaurant_name: str, product_names: dict) -> bytes:
    """Buyurtma uchun PDF hisob-faktura qaytaradi (bytes)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    y = height - 25 * mm

    c.setFillColor(colors.HexColor("#C8912F"))
    c.setFont("Helvetica-Bold", 20)
    c.drawString(20 * mm, y, "DalaBozor")
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 11)
    c.drawRightString(width - 20 * mm, y, "HISOB-FAKTURA")

    y -= 12 * mm
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, y, f"Buyurtma: {order.id}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Restoran: {restaurant_name}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"Yetkazish sanasi: {order.delivery_date}")
    y -= 6 * mm
    c.drawString(20 * mm, y, f"To'lov turi: {order.payment_type.value}")

    # Jadval sarlavhasi
    y -= 12 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Mahsulot")
    c.drawRightString(110 * mm, y, "Kg")
    c.drawRightString(150 * mm, y, "Narx")
    c.drawRightString(190 * mm, y, "Summa")
    y -= 3 * mm
    c.line(20 * mm, y, 190 * mm, y)

    c.setFont("Helvetica", 10)
    for item in order.items:
        y -= 7 * mm
        name = product_names.get(item.product_id, str(item.product_id))
        c.drawString(20 * mm, y, name)
        c.drawRightString(110 * mm, y, str(item.kg))
        c.drawRightString(150 * mm, y, _fmt(item.sell_price_per_kg))
        c.drawRightString(190 * mm, y, _fmt(item.subtotal))

    y -= 4 * mm
    c.line(20 * mm, y, 190 * mm, y)
    y -= 9 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(150 * mm, y, "Jami:")
    c.drawRightString(190 * mm, y, f"{_fmt(order.total_sum)} so'm")

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.grey)
    c.drawString(20 * mm, 15 * mm, "DalaBozor — dehqondan to'g'ridan-to'g'ri. Rahmat!")

    c.showPage()
    c.save()
    return buf.getvalue()
