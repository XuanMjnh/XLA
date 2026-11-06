"""Build the 10-slide TextureLab deck using the supplied LTM PowerPoint master.

Requires python-pptx and Pillow (authoring only, not desktop dependencies).
"""
from pathlib import Path
import argparse
import csv
import json
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.chart.data import CategoryChartData
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BLUE = '0B3F86'
INK = '111827'
GRAY = '526174'
LIGHT = 'EAF0F7'
ORANGE = 'D76A27'
WHITE = 'FFFFFF'


def rows(path):
    with (ROOT/path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def build(template, output):
    prs = Presentation(template)
    # Retain the original master (paper grid + PTIT logo), discard old content.
    for slide_id in list(prs.slides._sldIdLst):
        prs.part.drop_rel(slide_id.rId)
        prs.slides._sldIdLst.remove(slide_id)
    for child in list(prs._element):
        if child.tag.rsplit('}', 1)[-1] in {'custShowLst', 'sectionLst'}:
            prs._element.remove(child)
    prs.core_properties.title = 'Phân tích hướng và cấu trúc texture'
    prs.core_properties.subject = 'Bài tập lớn Xử lý ảnh – Nhóm 2, nhóm lớp 7'
    prs.core_properties.author = 'Nhóm 2 – Nhóm lớp 7'
    prs.core_properties.keywords = 'TextureLab, Sobel, Fourier, Directionality'
    prs.core_properties.comments = ''
    prs.slide_width = Inches(20)
    prs.slide_height = Inches(11.25)

    def box(s, x, y, w, h, fill=WHITE, line=None, rounded=True):
        sh = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
                                Inches(x), Inches(y), Inches(w), Inches(h))
        if rounded: sh.adjustments[0] = .12
        if fill: sh.fill.solid(); sh.fill.fore_color.rgb = RGBColor.from_string(fill)
        else: sh.fill.background()
        if line: sh.line.color.rgb = RGBColor.from_string(line); sh.line.width = Pt(.8)
        else: sh.line.fill.background()
        return sh

    def text(s, value, x, y, w, h, size=26, color=INK, bold=False, align=PP_ALIGN.LEFT):
        sh = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = sh.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(.03)
        tf.margin_top = tf.margin_bottom = Inches(.02)
        for i, line in enumerate(value.split('\n')):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line; p.alignment = align
            p.space_after = Pt(8); p.font.name = 'Roboto'; p.font.size = Pt(size)
            p.font.bold = bold; p.font.color.rgb = RGBColor.from_string(color)
        return sh

    def picture(s, path, x, y, w, h):
        path = ROOT/path
        iw, ih = Image.open(path).size
        scale = min(w/iw, h/ih)
        pw, ph = iw*scale, ih*scale
        return s.shapes.add_picture(str(path), Inches(x+(w-pw)/2), Inches(y+(h-ph)/2),
                                   width=Inches(pw), height=Inches(ph))

    def band(s, label, x, y, w, fill=BLUE):
        box(s, x, y, w, .62, fill)
        text(s, label, x+.15, y+.1, w-.3, .43, 25, WHITE, True)

    def slide(num, title, source):
        s = prs.slides.add_slide(prs.slide_layouts[0])
        for sh in list(s.shapes):
            sh._element.getparent().remove(sh._element)
        box(s, .5, .38, .9, .74, BLUE)
        text(s, f'{num:02d}', .55, .5, .8, .46, 26, WHITE, True, PP_ALIGN.CENTER)
        text(s, title, 1.65, .43, 16.4, .72, 36, BLUE, True)
        box(s, .65, 10.52, 18.7, .018, 'BDCBE0', rounded=False)
        text(s, 'TextureLab Desktop · Xử lý ảnh', .72, 10.68, 15.6, .32, 15, GRAY)
        text(s, f'NHÓM 2 · LỚP 7     {num:02d}/10', 16.2, 10.66, 3.12, .35, 15, BLUE, True, PP_ALIGN.RIGHT)
        return s

    def table(s, headers, data, x, y, widths, row_h=.8, size=25):
        for ri, values in enumerate([headers]+data):
            xx = x
            for ci, value in enumerate(values):
                box(s, xx, y+ri*row_h, widths[ci], row_h, BLUE if ri==0 else None,
                    BLUE if ri==0 else 'A2B1C4', False)
                text(s, str(value), xx+.14, y+ri*row_h+.14, widths[ci]-.28, row_h-.18,
                     size, WHITE if ri==0 else INK, ri==0)
                xx += widths[ci]

    def card(s, title, value, x, y, w, h=2.0):
        box(s, x, y, w, h, WHITE, 'BCCBDD')
        text(s, title, x+.25, y+.18, w-.5, .6, 27, BLUE, True)
        text(s, value, x+.25, y+.88, w-.5, h-.95, 25)

    s = slide(1, 'BÁO CÁO BÀI TẬP LỚN XỬ LÝ ẢNH', 'Học viện Công nghệ Bưu chính Viễn thông · Khoa Công nghệ thông tin 1 · Hà Nội, 2026')
    text(s, 'PHÂN TÍCH HƯỚNG', .9, 2.0, 11.4, 1.0, 46, INK, True)
    text(s, 'VÀ CẤU TRÚC TEXTURE', .9, 3.1, 11.4, 1.0, 42, BLUE, True)
    text(s, 'Sobel gradient · Histogram hướng\nPhân tích phổ Fourier · Directionality', .95, 4.55, 10.5, 1.35, 29, GRAY)
    text(s, 'Giảng viên hướng dẫn: TS. Nguyễn Tất Thắng', .95, 6.25, 10.9, .65, 28, BLUE)
    box(s, 12.2, 2.2, 7.0, 4.9, WHITE, BLUE)
    picture(s, 'results/windows/ui/desktop_analysis.png', 12.35, 2.35, 6.7, 4.55)
    band(s, 'TextureLab Desktop', 12.2, 7.35, 7.0)
    band(s, 'NHÓM BÀI TẬP LỚN 2 · NHÓM LỚP 7', .95, 7.35, 10.65)
    text(s, 'Nguyễn Trung Kiên – B23DCCN464\nPhùng Trần Đức Long – B23DCCN508', 1.0, 8.35, 9.3, 1.4, 25)
    text(s, 'Phạm Xuân Minh – B23DCCN564\nNguyễn Viết Vũ – B23DCCN946', 10.55, 8.35, 8.6, 1.4, 25)

    s = slide(2, 'Bài toán và quy ước hướng', 'Báo cáo: mục 1.1–1.3 và 2.1–2.6')
    card(s, 'ĐẦU VÀO', 'Ảnh xám / RGB, ảnh đơn khung\nVùng quan tâm ROI tùy chọn', .9, 1.7, 8.7, 2.45)
    card(s, 'ĐẦU RA', 'Histogram, góc đỉnh, nhiều đỉnh\nĐộ tập trung R, entropy, bản đồ hướng', 10.1, 1.7, 9.0, 2.45)
    band(s, 'Hai nhánh độc lập, cùng ảnh và cùng quy ước tọa độ', .9, 4.55, 18.2)
    for x, title, value in [(1.0,'01 · CHUẨN HÓA','Xám → ROI → Gaussian'), (7.15,'02 · PHÂN TÍCH','Sobel / phổ Fourier'), (13.3,'03 · DIỄN GIẢI','Góc + phân bố + cảnh báo')]:
        card(s, title, value, x, 5.55, 5.7, 1.95)
    box(s, .95, 8.0, 18.15, 1.7, LIGHT, BLUE)
    text(s, 'θ ∈ [0°, 180°)     ·     0° nằm ngang     ·     90° thẳng đứng', 1.25, 8.22, 17.4, .6, 31, BLUE, True)
    text(s, 'Đo hướng cấu trúc ngược chiều kim đồng hồ; pháp tuyến gradient / phổ lệch hướng vân 90°.', 1.25, 8.96, 17.4, .5, 25)

    s = slide(3, 'Hai phương pháp phân tích hướng', 'Báo cáo: mục 2.2–2.5, 3.1–3.4 · Cấu hình mặc định trong texture/analysis.py')
    for x,title,color in [(.95,'NHÁNH KHÔNG GIAN · SOBEL',BLUE),(10.25,'NHÁNH TẦN SỐ · FOURIER',ORANGE)]:
        box(s,x,1.7,8.8,7.0,WHITE,'BCCBDD');band(s,title,x,1.7,8.8,color)
    text(s,'01   Sobel 5 × 5 → Gₓ, Gᵧ\n02   Độ lớn M = √(Gₓ² + Gᵧ²)\n03   Loại gradient yếu và biên\n04   Bỏ phiếu tuyến tính, trọng số M²\n05   Histogram tuần hoàn, nội suy đỉnh',1.25,2.8,8.15,4.0,29)
    text(s,'θ = [atan2(−Gᵧ, Gₓ) + 90°] mod 180°',1.25,7.1,8.1,1.1,26,BLUE,True)
    text(s,'01   Trừ trung bình → cửa sổ Hann\n02   F = FFT2(I), công suất P = |F|²\n03   Lưới tần số riêng theo H và W\n04   Gom năng lượng trong vành tần số\n05   Histogram hướng, nhiều đỉnh',10.55,2.8,8.1,4.0,29)
    text(s,'θ = [atan2(−fᵧ, fₓ) + 90°] mod 180°',10.55,7.1,8.1,1.1,26,ORANGE,True)
    text(s,'Chung: Gaussian σ = 1 px · 180 bin · Làm trơn histogram 2° · Dải Fourier 0,02–0,45 chu kỳ/pixel',1.0,9.15,18.0,.85,26,GRAY)

    s = slide(4, 'Ứng dụng TextureLab Desktop', 'Báo cáo: mục 4.1–4.4 · Ảnh: results/windows/ui/desktop_analysis.png')
    box(s,.85,1.65,12.75,7.75,WHITE,BLUE)
    picture(s,'results/windows/ui/desktop_analysis.png',1.0,1.82,12.45,7.4)
    card(s,'QUY TRÌNH PHÂN TÍCH','Ảnh đơn / xử lý lô\nROI: chuột / tọa độ\nChạy nền, dừng giữa các ảnh',14.0,1.65,5.15,3.0)
    card(s,'XUẤT VÀ ĐỐI CHIẾU','Ảnh trung gian, thang màu\nCSV / JSON / PNG / HTML\nNPZ, ZIP và CSV Fiji',14.0,4.95,5.15,3.0)
    band(s,'63 kiểm thử đạt trên Windows',14.0,8.4,5.15)
    text(s,'Bộ màu sáng cố định · Tham số và ROI có thể thu gọn · Hai giao diện dùng chung lõi thuật toán',1.0,9.65,18.1,.55,25,GRAY)

    s = slide(5, 'Thiết kế thực nghiệm có nhãn', 'Báo cáo: mục 5.1 · results/windows/experiments/accuracy.csv và các CSV ablation')
    box(s,.95,1.7,6.1,3.8,BLUE)
    text(s,'240',1.3,2.02,5.4,1.8,96,WHITE,True,PP_ALIGN.CENTER)
    text(s,'LƯỢT ĐÁNH GIÁ CHÍNH',1.25,3.88,5.5,.6,28,WHITE,True,PP_ALIGN.CENTER)
    text(s,'12 góc × 4 mức nhiễu × 5 seed',1.2,4.65,5.6,.5,24,WHITE,False,PP_ALIGN.CENTER)
    card(s,'DỮ LIỆU CHÍNH','Ảnh vân sin 256 × 256, chu kỳ 16 px\nNhiễu σn: 0; 0,05; 0,15; 0,30\nClip và lượng tử hóa uint8 trước đo',7.6,1.7,11.5,3.8)
    table(s,['Khảo sát','Số lượt','Mục đích'],[['Gaussian','144','Ảnh hưởng tiền xử lý'],['Số bin','144','Độ phân giải và sai số góc'],['Hann','72','Rò phổ và độ ổn định đỉnh']],.95,6.05,[5.0,2.2,10.95],.8,25)
    text(s,'240 lượt tương ứng 192 ảnh khác nhau: ở mức không nhiễu, thay seed không tạo ảnh mới.',1.0,9.6,18.1,.6,25,BLUE,True)

    accuracy=rows('results/windows/experiments/accuracy_summary.csv')
    s = slide(6,'Sai số góc trên bộ vân sin tổng hợp','Báo cáo: mục 5.2 · Nguồn: results/windows/experiments/accuracy_summary.csv')
    box(s,.95,1.75,12.5,7.8,WHITE,'BCCBDD')
    data=CategoryChartData();data.categories=[r['noise_sigma'].replace('.',',') for r in accuracy]
    data.add_series('Sobel',[float(r['spatial_mae']) for r in accuracy])
    data.add_series('Fourier',[float(r['fourier_mae']) for r in accuracy])
    chart=s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(1.2),Inches(2.3),Inches(11.9),Inches(6.6),data).chart
    chart.has_legend=True;chart.legend.position=XL_LEGEND_POSITION.BOTTOM
    chart.legend.include_in_layout=False;chart.legend.font.name='Roboto';chart.legend.font.size=Pt(23)
    chart.category_axis.has_title=True;chart.category_axis.axis_title.text_frame.text='Độ lệch chuẩn nhiễu σn (trước clip)'
    chart.value_axis.has_title=True;chart.value_axis.axis_title.text_frame.text='MAE góc trục (độ)'
    chart.value_axis.minimum_scale=0;chart.value_axis.maximum_scale=1.1;chart.value_axis.major_unit=.2
    for axis in [chart.category_axis,chart.value_axis]:
        axis.tick_labels.font.name='Roboto';axis.tick_labels.font.size=Pt(20)
        for p in axis.axis_title.text_frame.paragraphs:p.font.name='Roboto';p.font.size=Pt(21)
    for series,color in zip(chart.series,[BLUE,ORANGE]):
        series.format.line.color.rgb=RGBColor.from_string(color);series.format.line.width=Pt(3)
        series.marker.size=10;series.marker.format.fill.solid();series.marker.format.fill.fore_color.rgb=RGBColor.from_string(color)
    band(s,'TẠI σn = 0,30',14.0,1.75,5.1)
    text(s,f"{float(accuracy[-1]['spatial_mae']):.4f}°".replace('.',','),14.15,2.8,4.8,.9,49,BLUE,True)
    text(s,'MAE Sobel',14.15,3.8,4.8,.55,27,GRAY)
    text(s,f"{float(accuracy[-1]['fourier_mae']):.4f}°".replace('.',','),14.15,4.85,4.8,.9,49,ORANGE,True)
    text(s,'MAE Fourier',14.15,5.85,4.8,.55,27,GRAY)
    text(s,'Fourier giữ đỉnh ổn định hơn trên bộ vân sin tuần hoàn đã chọn.',14.1,7.1,4.95,1.8,28,INK,True)

    s = slide(7,'Hai hệ vân vuông góc: giới hạn của một góc','Báo cáo: mục 5.4–5.5 · Dữ liệu: crossing_030_120.png, kết quả Python tại results/windows/fiji/')
    box(s,.95,1.75,4.4,5.1,WHITE,'BCCBDD')
    picture(s,'data/samples/crossing_030_120.png',1.2,2.05,3.9,3.9)
    text(s,'Hai vân: 30° và 120°',1.1,6.15,4.1,.5,24,BLUE,True,PP_ALIGN.CENTER)
    box(s,5.7,1.75,13.4,5.1,WHITE,'BCCBDD')
    picture(s,'results/windows/fiji/crossing_030_120/python/histogram.png',5.95,1.95,12.9,4.65)
    card(s,'FOURIER','Hai đỉnh ≈ 30,01° và 120,01°\nR gần 0 do hai trục triệt tiêu',.95,7.25,8.8,2.45)
    card(s,'SOBEL','Đỉnh ≈ 74,84° và 164,86°\nGradient tổng không tách từng vân',10.25,7.25,8.85,2.45)

    comparison=json.loads((ROOT/'results/windows/fiji/comparison_summary.json').read_text())['methods']
    s = slide(8,'Đối chiếu Directionality chính thức','Báo cáo: mục 5.8 · results/windows/fiji/comparison_summary.json và demo/')
    band(s,'15 ảnh · 14 ảnh có tín hiệu · 11 ảnh một hướng có nhãn',.95,1.65,18.15)
    text(s,'MAE của histogram thô đã căn chỉnh, trên 11 ảnh một hướng',1.0,2.65,18.0,.65,29,BLUE,True)
    values=[]
    for key,name in [('spatial','Sobel'),('fourier','Fourier')]:
        m=comparison[key]
        values.append([name,f"{m['single_python_raw_mae_deg']:.4f}°".replace('.',','),f"{m['single_fiji_raw_mae_deg']:.4f}°".replace('.',','),f"{m['single_mean_peak_difference_deg']:.4f}°".replace('.',',')])
    table(s,['Nhánh','MAE Python','MAE Fiji','Δ đỉnh TB'],values,.95,3.45,[3.4,4.9,4.9,4.95],.85,27)
    box(s,.95,6.4,9.15,3.45,WHITE,'BCCBDD')
    picture(s,'results/windows/fiji/demo/fourier_components_plot.png',1.15,6.5,8.75,3.2)
    text(s,'ImageJ 1.54p · Directionality 2.3.0\nGaussian σ = 1 · 180 bin · 0–180°\nKhông đồng nhất Amount với R.\nẢnh nhiều hướng: so sánh cả phân bố.',10.65,6.65,8.2,3.15,28)

    sigma=rows('results/windows/experiments/ablation_sigma_summary.csv')
    hann=rows('results/windows/experiments/ablation_hann_summary.csv')
    runtime=rows('results/windows/experiments/runtime.csv')
    s = slide(9,'Khảo sát tham số và chi phí xử lý','Báo cáo: mục 3.7, 5.6–5.7 · CSV ablation, runtime và results/windows/optimization/voting.csv')
    card(s,'GAUSSIAN: σ TỪ 0 → 2 PX',f"MAE Sobel: {float(sigma[0]['spatial_mae']):.4f}° → {float(sigma[-1]['spatial_mae']):.4f}°\nLàm trơn ổn định gradient có nhiễu.".replace('.',','),.95,1.75,8.8,2.5)
    card(s,'HANN: TẮT → BẬT',f"MAE Fourier: {float(hann[0]['fourier_mae']):.4f}° → {float(hann[1]['fourier_mae']):.4f}°\nGiảm ảnh hưởng gián đoạn ở biên.".replace('.',','),10.25,1.75,8.85,2.5)
    text(s,'Thời gian lõi · trung vị 5 lần sau 1 lần làm nóng',1.0,4.75,18.1,.6,29,BLUE,True)
    table(s,['Ảnh vuông']+[r['size']+' px' for r in runtime],
          [['Thời gian']+[f"{float(r['median_ms']):.2f} ms".replace('.',',') for r in runtime]],
          .95,5.6,[4.15,3.5,3.5,3.5,3.5],.85,25)
    box(s,.95,7.85,18.15,1.9,LIGHT,BLUE)
    text(s,'Tăng số bin không luôn giảm sai số. Microbenchmark add.at / bincount có tỉ số tốc độ 0,988–1,034; chưa đủ bằng chứng tăng tốc rõ rệt.',1.25,8.15,17.5,1.2,28)

    s=slide(10,'Kết luận và hướng phát triển','Báo cáo: Chương 6 · Mã nguồn, dữ liệu và hướng dẫn tái lập trong README.md')
    card(s,'ĐÃ HOÀN THÀNH','Hai nhánh Sobel và Fourier dùng chung quy ước.\nỨng dụng desktop, CLI, ROI và xuất dữ liệu.\nThực nghiệm có nhãn và đối chiếu Fiji.',.95,1.75,11.0,3.5)
    card(s,'PHẠM VI KẾT LUẬN','Dữ liệu tổng hợp có kiểm soát.\nChưa đánh giá ảnh tự nhiên có nhãn.\nChưa kiểm chứng trên macOS.',12.45,1.75,6.65,3.5)
    card(s,'HƯỚNG PHÁT TRIỂN','Ảnh vật liệu / hiển vi có nhãn độc lập.\nTrường hướng cục bộ, phân tích đa thang.\nSo khớp tập nhiều đỉnh và toàn phân bố.',.95,5.7,11.0,3.35)
    box(s,12.45,5.7,6.65,3.35,BLUE)
    text(s,'Histogram nhiều đỉnh\nbổ sung thông tin\ncho độ tập trung R.',12.85,6.22,5.9,2.3,36,WHITE,True)
    text(s,'Cảm ơn thầy và các bạn đã lắng nghe!',1.0,9.55,18.1,.65,32,BLUE,True,PP_ALIGN.CENTER)

    assert len(prs.slides)==10
    forbidden=['CẦN ĐIỀN','NHÓM 19','Ngô Văn Quyền','Code Survival','Client–Server','Xuanminh.io.vn']
    all_text='\n'.join(sh.text for sl in prs.slides for sh in sl.shapes if sh.has_text_frame)
    assert not any(token in all_text for token in forbidden)
    for si,sl in enumerate(prs.slides,1):
        for sh in sl.shapes:
            assert sh.left>=0 and sh.top>=0 and sh.left+sh.width<=prs.slide_width+10 and sh.top+sh.height<=prs.slide_height+10,(si,sh.name)
    output.parent.mkdir(parents=True,exist_ok=True)
    prs.save(output)
    print(f'Saved {len(prs.slides)} slides: {output}')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=ROOT/'thuyet_trinh/TextureLab_Desktop_10_slides.pptx')
    args=parser.parse_args()
    build(args.template,args.out)
