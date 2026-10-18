"""Detailed PDF report generator for BugSight QA."""

from __future__ import annotations

import html
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BUG_CLASSES = [
    "missing_texture",
    "texture_glitch",
    "z_fighting",
    "screen_tear",
    "uv_stretch",
    "color_corruption",
]

_GUIDE_FR = {
    "missing_texture": {
        "title": "Texture manquante",
        "description": "Une texture attendue n'est pas disponible, n'est pas chargée ou n'est pas correctement assignée à l'objet.",
        "impact": "Objet affiché en blanc, noir, avec un matériau par défaut ou avec un artefact visuel.",
        "checks": "Vérifier le chemin de l'asset, le nom de la ressource, le bundle de livraison et les erreurs de chargement dans les logs.",
        "fix": "Réimporter la texture, corriger la référence du matériau, vérifier les règles d'inclusion dans le build et ajouter un fallback visuel contrôlé.",
        "priority": "Haute",
    },
    "texture_glitch": {
        "title": "Texture corrompue",
        "description": "La texture présente des blocs, du bruit ou des fragments qui peuvent indiquer une ressource mal encodée ou un problème mémoire GPU.",
        "impact": "Dégradation de la lisibilité et de la qualité visuelle; le défaut peut être intermittent selon la scène.",
        "checks": "Comparer l'asset source et la texture en jeu, tester les formats de compression, surveiller la mémoire vidéo et reproduire sur plusieurs GPU.",
        "fix": "Réencoder la texture, ajuster la compression/mipmaps, réduire la résolution si nécessaire et corriger les allocations ou la durée de vie des ressources GPU.",
        "priority": "Haute",
    },
    "z_fighting": {
        "title": "Z-fighting / conflit de profondeur",
        "description": "Deux surfaces presque coplanaires se disputent la même position dans le buffer de profondeur.",
        "impact": "Scintillement, motifs instables ou alternance visible entre deux surfaces.",
        "checks": "Identifier les meshes superposés, vérifier les transformations, la caméra, le near/far clip et la précision du depth buffer.",
        "fix": "Éloigner les surfaces, supprimer le doublon, utiliser un offset de profondeur maîtrisé ou améliorer la précision de la caméra et du depth buffer.",
        "priority": "Haute",
    },
    "screen_tear": {
        "title": "Screen tearing",
        "description": "L'image est composée de portions de plusieurs frames à cause d'une désynchronisation entre rendu et rafraîchissement de l'écran.",
        "impact": "Lignes horizontales et rupture de continuité pendant les mouvements de caméra ou les déplacements rapides.",
        "checks": "Comparer V-Sync, G-Sync/FreeSync, fréquence d'affichage, limite FPS et comportement en mode fenêtré ou plein écran.",
        "fix": "Configurer V-Sync ou une synchronisation adaptative, limiter les FPS légèrement sous la fréquence écran et tester les paramètres du pilote graphique.",
        "priority": "Moyenne",
    },
    "uv_stretch": {
        "title": "Étirement UV",
        "description": "Les coordonnées UV ne correspondent pas correctement à la géométrie, ce qui étire ou compresse la texture.",
        "impact": "Motifs déformés, échelle incohérente ou texture qui semble tirer le long d'une face.",
        "checks": "Afficher les UV dans l'outil 3D, vérifier les coutures, les transformations non appliquées et le canal UV utilisé par le shader.",
        "fix": "Corriger le dépliage UV, appliquer les transformations, vérifier le canal UV et réexporter le mesh avec ses tangentes cohérentes.",
        "priority": "Moyenne",
    },
    "color_corruption": {
        "title": "Corruption des couleurs",
        "description": "Les couleurs rendues ne correspondent pas à l'asset ou au matériau attendu, souvent à cause d'un espace colorimétrique ou d'un ordre de canaux incorrect.",
        "impact": "Teintes anormales, couleurs inversées ou rendu très différent entre l'éditeur et le build.",
        "checks": "Vérifier sRGB/linear, le format d'image, l'ordre RGBA/BGRA, le shader, les post-process et les profils de couleur.",
        "fix": "Corriger l'import colorimétrique, le mapping des canaux et le shader; régénérer les assets puis valider sur la cible de déploiement.",
        "priority": "Moyenne",
    },
}


_GUIDE_EN = {
    "missing_texture": {
        "title": "Missing texture",
        "description": "An expected texture is unavailable, not loaded, or not correctly assigned to the object.",
        "impact": "Object shown in white, black, with a default material, or with a visual artifact.",
        "checks": "Check the asset path, resource name, delivery bundle and loading errors in the logs.",
        "fix": "Re-import the texture, fix the material reference, check the build inclusion rules and add a controlled visual fallback.",
        "priority": "High",
    },
    "texture_glitch": {
        "title": "Corrupted texture",
        "description": "The texture shows blocks, noise or fragments that may indicate a badly encoded resource or a GPU memory problem.",
        "impact": "Reduced readability and visual quality; the defect may be intermittent depending on the scene.",
        "checks": "Compare the source asset with the in-game texture, test compression formats, monitor video memory and reproduce on several GPUs.",
        "fix": "Re-encode the texture, adjust compression/mipmaps, lower the resolution if needed and fix GPU resource allocations or lifetimes.",
        "priority": "High",
    },
    "z_fighting": {
        "title": "Z-fighting / depth conflict",
        "description": "Two almost coplanar surfaces compete for the same position in the depth buffer.",
        "impact": "Flickering, unstable patterns or visible alternation between two surfaces.",
        "checks": "Identify overlapping meshes, check transforms, the camera, the near/far clip and the depth buffer precision.",
        "fix": "Move the surfaces apart, remove the duplicate, use a controlled depth offset or improve camera and depth buffer precision.",
        "priority": "High",
    },
    "screen_tear": {
        "title": "Screen tearing",
        "description": "The image is made of slices of several frames because rendering and display refresh are out of sync.",
        "impact": "Horizontal lines and broken continuity during camera movement or fast motion.",
        "checks": "Compare V-Sync, G-Sync/FreeSync, display refresh rate, FPS cap and behavior in windowed vs fullscreen mode.",
        "fix": "Enable V-Sync or adaptive sync, cap the FPS slightly below the refresh rate and test the graphics driver settings.",
        "priority": "Medium",
    },
    "uv_stretch": {
        "title": "UV stretching",
        "description": "UV coordinates do not match the geometry correctly, stretching or squashing the texture.",
        "impact": "Distorted patterns, inconsistent scale or a texture that seems pulled along a face.",
        "checks": "Display the UVs in the 3D tool, check seams, unapplied transforms and the UV channel used by the shader.",
        "fix": "Fix the UV unwrap, apply transforms, check the UV channel and re-export the mesh with consistent tangents.",
        "priority": "Medium",
    },
    "color_corruption": {
        "title": "Color corruption",
        "description": "Rendered colors do not match the expected asset or material, often because of a wrong color space or channel order.",
        "impact": "Abnormal tints, inverted colors or a render very different between the editor and the build.",
        "checks": "Check sRGB/linear, the image format, RGBA/BGRA order, the shader, post-processing and color profiles.",
        "fix": "Fix the color import, channel mapping and shader; regenerate the assets and validate on the deployment target.",
        "priority": "Medium",
    },
}

GUIDES = {"fr": _GUIDE_FR, "en": _GUIDE_EN}
SUPPORTED_LANGS = ("fr", "en")
DEFAULT_LANG = "fr"

# UI strings per language. Placeholders use str.format syntax.
TEXTS = {
    "fr": {
        "doc_title": "BugSight QA - Rapport détaillé",
        "title": "BugSight QA — Rapport de scan détaillé",
        "meta": "<b>Généré le :</b> {generated}<br/><b>Utilisateur :</b> {user}<br/><b>Analyses image persistées :</b> {total}<br/><b>Objectif :</b> détection de défauts visuels par modèle YOLOv8.",
        "image_results": "Résultats des analyses d'images",
        "th_indicator": "Indicateur",
        "th_result": "Résultat",
        "th_interp": "Interprétation",
        "row_total": "Analyses totales",
        "row_total_d": "Nombre de scans image inclus dans ce rapport.",
        "row_buggy": "Images avec anomalie",
        "row_buggy_d": "Images nécessitant une vérification QA.",
        "row_clean": "Images propres",
        "row_clean_d": "Aucune détection retenue par le modèle.",
        "row_rate": "Taux d'anomalie",
        "row_rate_d": "Part des images contenant au moins une détection.",
        "triage_note": "Le taux de détection est un indicateur de triage et ne constitue pas à lui seul une preuve définitive du bug. Les résultats doivent être confirmés par une revue humaine, en particulier pour les scores de confiance faibles.",
        "dist_images": "Distribution des défauts — images uniquement",
        "th_type": "Type",
        "th_occ": "Occurrences",
        "th_share_img": "Part des détections image",
        "th_severity": "Sévérité",
        "th_short": "Diagnostic court",
        "guide_images": "Guide de diagnostic et de résolution — images",
        "priority_word": "priorité",
        "g_description": "Description",
        "g_impact": "Impact probable",
        "g_checks": "Vérifications QA",
        "g_fix": "Méthode de résolution",
        "no_image_bugs": "Aucune détection de bug n'a été enregistrée dans les analyses d'images.",
        "video_results": "Résultats des analyses vidéo",
        "video_note": "Cette section est indépendante des résultats image. Les taux, occurrences, frames et recommandations ci-dessous concernent uniquement la vidéo analysée.",
        "video_h": "Analyse vidéo",
        "th_detail": "Détail",
        "v_total": "Frames dans la vidéo",
        "v_total_d": "Nombre total de frames du fichier.",
        "v_analyzed": "Frames analysées",
        "v_analyzed_d": "Échantillon réellement envoyé au modèle.",
        "v_buggy": "Frames avec bug",
        "v_buggy_d": "Frames à revoir en priorité.",
        "v_rate": "Taux de bug vidéo",
        "v_rate_d": "Ratio des frames problématiques dans l'échantillon.",
        "v_dur": "Durée / FPS",
        "v_dur_d": "Contexte temporel du scan.",
        "dist_video": "Distribution des défauts — vidéo uniquement",
        "th_occ_video": "Occurrences vidéo",
        "th_share": "Part",
        "fix_video": "Méthodes de résolution — vidéos",
        "checks_label": "Vérifications :",
        "fix_label": "Résolution :",
        "no_video_bugs": "Aucune classe de bug n'a été enregistrée dans cette analyse vidéo.",
        "timeline": "Timeline des frames problématiques",
        "th_frame": "Frame",
        "th_time": "Temps",
        "th_detections": "Détections",
        "th_types": "Types détectés",
        "th_action": "Action recommandée",
        "unknown": "inconnu",
        "capture_action": "Capturer la frame et reproduire la scène.",
        "tech_details": "Détails techniques des détections image",
        "no_image_det": "Aucune détection image n'a été enregistrée. Le résultat est favorable pour l'échantillon analysé.",
        "unknown_file": "fichier inconnu",
        "det_line": "<b>{index}. {filename}</b> — {n} détection(s), résolution {width} × {height}",
        "th_conf": "Confiance",
        "th_bbox": "Bounding box",
        "th_reading": "Lecture QA",
        "conf_high": "forte",
        "conf_mid": "à confirmer",
        "conf_low": "faible — revue humaine prioritaire",
        "image_pct": "image",
        "default_fix": "Vérifier la scène et le pipeline de rendu.",
        "sev_critical": "Critique",
        "sev_high": "Élevée",
        "sev_moderate": "Modérée",
        "sev_none": "Aucune anomalie détectée",
        "medium_image": "image",
        "medium_video": "vidéo",
        "rem_critical": "Bloquer la validation {medium}, isoler les classes dominantes et lancer une investigation du pipeline de rendu avant toute release.",
        "rem_high": "Créer des tickets {medium} par type de défaut, commencer par les classes dominantes et ajouter une reproduction minimale pour chaque anomalie.",
        "rem_moderate": "Revoir manuellement les détections {medium}, corriger les défauts confirmés et ajouter une campagne de non-régression.",
        "rem_none": "Conserver les paramètres de scan {medium} et lancer une nouvelle campagne sur des scènes ou configurations différentes.",
        "plan_image": "Plan de remédiation — images uniquement",
        "r_image_rate": "Taux image",
        "r_image_priority": "Priorité image",
        "r_action": "Action immédiate",
        "r_validation": "Validation",
        "r_image_validation": "Relancer les mêmes images après correction et comparer le nombre de détections, la confiance et les bounding boxes.",
        "plan_video": "Plan de remédiation — vidéos uniquement",
        "r_video_rate": "Taux vidéo",
        "r_video_priority": "Priorité vidéo",
        "r_video_validation": "Relancer la vidéo après correction et comparer les frames problématiques, les timestamps et la distribution des classes.",
        "video_none_h": "Résultats vidéo",
        "video_none": "Aucune analyse vidéo n'est incluse dans ce rapport. Les résultats image restent séparés et ne sont pas mélangés à une statistique vidéo absente.",
        "limits": "Limites du rapport : la confiance du modèle mesure la probabilité de la classe prédite, mais ne remplace pas la reproduction du défaut dans le jeu. Les procédures proposées sont des pistes de diagnostic QA et doivent être adaptées au moteur, au shader et à la plateforme ciblée.",
    },
    "en": {
        "doc_title": "BugSight QA - Detailed report",
        "title": "BugSight QA — Detailed scan report",
        "meta": "<b>Generated on:</b> {generated}<br/><b>User:</b> {user}<br/><b>Stored image analyses:</b> {total}<br/><b>Purpose:</b> visual defect detection with a YOLOv8 model.",
        "image_results": "Image analysis results",
        "th_indicator": "Indicator",
        "th_result": "Result",
        "th_interp": "Interpretation",
        "row_total": "Total analyses",
        "row_total_d": "Number of image scans included in this report.",
        "row_buggy": "Images with anomalies",
        "row_buggy_d": "Images that need a QA check.",
        "row_clean": "Clean images",
        "row_clean_d": "No detection retained by the model.",
        "row_rate": "Anomaly rate",
        "row_rate_d": "Share of images containing at least one detection.",
        "triage_note": "The detection rate is a triage indicator and is not definitive proof of a bug on its own. Results must be confirmed by a human review, especially for low confidence scores.",
        "dist_images": "Defect distribution — images only",
        "th_type": "Type",
        "th_occ": "Occurrences",
        "th_share_img": "Share of image detections",
        "th_severity": "Severity",
        "th_short": "Short diagnosis",
        "guide_images": "Diagnosis and resolution guide — images",
        "priority_word": "priority",
        "g_description": "Description",
        "g_impact": "Likely impact",
        "g_checks": "QA checks",
        "g_fix": "Resolution method",
        "no_image_bugs": "No bug detection was recorded in the image analyses.",
        "video_results": "Video analysis results",
        "video_note": "This section is independent from the image results. The rates, occurrences, frames and recommendations below only concern the analyzed video.",
        "video_h": "Video analysis",
        "th_detail": "Detail",
        "v_total": "Frames in the video",
        "v_total_d": "Total number of frames in the file.",
        "v_analyzed": "Frames analyzed",
        "v_analyzed_d": "Sample actually sent to the model.",
        "v_buggy": "Frames with bugs",
        "v_buggy_d": "Frames to review first.",
        "v_rate": "Video bug rate",
        "v_rate_d": "Ratio of problematic frames in the sample.",
        "v_dur": "Duration / FPS",
        "v_dur_d": "Time context of the scan.",
        "dist_video": "Defect distribution — video only",
        "th_occ_video": "Video occurrences",
        "th_share": "Share",
        "fix_video": "Resolution methods — videos",
        "checks_label": "Checks:",
        "fix_label": "Resolution:",
        "no_video_bugs": "No bug class was recorded in this video analysis.",
        "timeline": "Timeline of problematic frames",
        "th_frame": "Frame",
        "th_time": "Time",
        "th_detections": "Detections",
        "th_types": "Detected types",
        "th_action": "Recommended action",
        "unknown": "unknown",
        "capture_action": "Capture the frame and reproduce the scene.",
        "tech_details": "Technical details of image detections",
        "no_image_det": "No image detection was recorded. The result is favorable for the analyzed sample.",
        "unknown_file": "unknown file",
        "det_line": "<b>{index}. {filename}</b> — {n} detection(s), resolution {width} × {height}",
        "th_conf": "Confidence",
        "th_bbox": "Bounding box",
        "th_reading": "QA reading",
        "conf_high": "strong",
        "conf_mid": "to confirm",
        "conf_low": "low — human review first",
        "image_pct": "image",
        "default_fix": "Check the scene and the rendering pipeline.",
        "sev_critical": "Critical",
        "sev_high": "High",
        "sev_moderate": "Moderate",
        "sev_none": "No anomaly detected",
        "medium_image": "image",
        "medium_video": "video",
        "rem_critical": "Block the {medium} sign-off, isolate the dominant classes and investigate the rendering pipeline before any release.",
        "rem_high": "Create {medium} tickets per defect type, start with the dominant classes and add a minimal reproduction for each anomaly.",
        "rem_moderate": "Manually review the {medium} detections, fix the confirmed defects and add a regression campaign.",
        "rem_none": "Keep the {medium} scan settings and run a new campaign on different scenes or configurations.",
        "plan_image": "Remediation plan — images only",
        "r_image_rate": "Image rate",
        "r_image_priority": "Image priority",
        "r_action": "Immediate action",
        "r_validation": "Validation",
        "r_image_validation": "Re-run the same images after the fix and compare the number of detections, confidence and bounding boxes.",
        "plan_video": "Remediation plan — videos only",
        "r_video_rate": "Video rate",
        "r_video_priority": "Video priority",
        "r_video_validation": "Re-run the video after the fix and compare the problematic frames, timestamps and class distribution.",
        "video_none_h": "Video results",
        "video_none": "No video analysis is included in this report. Image results stay separate and are not mixed with a missing video statistic.",
        "limits": "Report limits: model confidence measures the probability of the predicted class but does not replace reproducing the defect in the game. The proposed procedures are QA diagnostic leads and must be adapted to the engine, shader and target platform.",
    },
}


def normalize_lang(lang) -> str:
    lang = (lang or DEFAULT_LANG).lower()[:2]
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def pct(value) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def make_table(data, widths, header_color="#4f46e5", body_color="#f9fafb", font_size=8):
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("LEADING", (0, 0), (-1, -1), font_size + 2),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(body_color)]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def generate_report(
    predictions: list[dict],
    user_name: str = "QA Tester",
    stats: dict | None = None,
    video_result: dict | None = None,
    lang: str = DEFAULT_LANG,
) -> bytes:
    """Generate a detailed PDF report from image predictions and optional video analysis.

    ``lang`` selects the report language ("fr" or "en"; anything else falls back to French).
    """
    lang = normalize_lang(lang)
    tx = TEXTS[lang]
    guides = GUIDES[lang]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=tx["doc_title"],
        author="BugSight QA",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=21,
        leading=25,
        textColor=colors.HexColor("#4338ca"),
        spaceAfter=8,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1f2937"),
        spaceBefore=12,
        spaceAfter=7,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading3"],
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#374151"),
        spaceBefore=8,
        spaceAfter=4,
    )
    normal = ParagraphStyle(
        "Normal",
        parent=styles["Normal"],
        fontSize=8.8,
        leading=12,
        textColor=colors.HexColor("#4b5563"),
    )
    small = ParagraphStyle("Small", parent=normal, fontSize=7.5, leading=10)
    bug = ParagraphStyle("Bug", parent=normal, textColor=colors.HexColor("#b91c1c"))
    note = ParagraphStyle(
        "Note",
        parent=normal,
        backColor=colors.HexColor("#eff6ff"),
        borderColor=colors.HexColor("#bfdbfe"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=6,
    )

    elements = []
    total = len(predictions)
    buggy = sum(1 for p in predictions if p.get("has_bug"))
    clean = total - buggy
    bug_rate = buggy / total * 100 if total else 0
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    elements += [
        Paragraph(tx["title"], title),
        Paragraph(tx["meta"].format(generated=generated, user=esc(user_name), total=total), normal),
        Spacer(1, 8),
    ]
    elements.append(Paragraph(tx["image_results"], h1))
    elements.append(
        make_table(
            [
                [tx["th_indicator"], tx["th_result"], tx["th_interp"]],
                [tx["row_total"], str(total), tx["row_total_d"]],
                [tx["row_buggy"], str(buggy), tx["row_buggy_d"]],
                [tx["row_clean"], str(clean), tx["row_clean_d"]],
                [tx["row_rate"], f"{bug_rate:.1f}%", tx["row_rate_d"]],
            ],
            [48 * mm, 30 * mm, 91 * mm],
        )
    )
    elements.append(Paragraph(tx["triage_note"], note))

    # ── Image-only results ─────────────────────────────────
    image_class_counts = dict.fromkeys(BUG_CLASSES, 0)
    for prediction in predictions:
        for detection in prediction.get("detections", []):
            name = detection.get("class_name", "")
            if name in image_class_counts:
                image_class_counts[name] += 1

    image_classes = [name for name in BUG_CLASSES if image_class_counts[name] > 0]
    elements.append(Paragraph(tx["dist_images"], h1))
    if image_classes:
        dist = [
            [tx["th_type"], tx["th_occ"], tx["th_share_img"], tx["th_severity"], tx["th_short"]]
        ]
        all_image_detections = sum(image_class_counts.values()) or 1
        for name in image_classes:
            guide = guides[name]
            dist.append(
                [
                    Paragraph(esc(guide["title"]), small),
                    str(image_class_counts[name]),
                    f"{image_class_counts[name] / all_image_detections * 100:.1f}%",
                    guide["priority"],
                    Paragraph(esc(guide["description"]), small),
                ]
            )
        elements.append(
            make_table(
                dist,
                [35 * mm, 20 * mm, 32 * mm, 20 * mm, 62 * mm],
                header_color="#dc2626",
                body_color="#fef2f2",
                font_size=7.2,
            )
        )

        elements.append(Paragraph(tx["guide_images"], h1))
        for name in image_classes:
            guide = guides[name]
            elements.append(
                Paragraph(
                    f"<b>{esc(guide['title'])}</b> — {tx['priority_word']} {esc(guide['priority'])}",
                    h2,
                )
            )
            guide_rows = [
                [tx["g_description"], Paragraph(esc(guide["description"]), small)],
                [tx["g_impact"], Paragraph(esc(guide["impact"]), small)],
                [tx["g_checks"], Paragraph(esc(guide["checks"]), small)],
                [tx["g_fix"], Paragraph(esc(guide["fix"]), small)],
            ]
            elements.append(
                make_table(
                    guide_rows,
                    [37 * mm, 132 * mm],
                    header_color="#475569",
                    body_color="#f8fafc",
                    font_size=7.5,
                )
            )
    else:
        elements.append(Paragraph(tx["no_image_bugs"], normal))

    # ── Video-only results ─────────────────────────────────
    if video_result and video_result.get("analyzed_frames", 0) > 0:
        elements.append(PageBreak())
        elements.append(Paragraph(tx["video_results"], title))
        elements.append(Paragraph(tx["video_note"], note))
        elements.append(Paragraph(tx["video_h"], h1))
        v_total = video_result.get("analyzed_frames", 0)
        v_buggy = video_result.get("buggy_frames", 0)
        elements.append(
            make_table(
                [
                    [tx["th_indicator"], tx["th_result"], tx["th_detail"]],
                    [tx["v_total"], str(video_result.get("total_frames", 0)), tx["v_total_d"]],
                    [tx["v_analyzed"], str(v_total), tx["v_analyzed_d"]],
                    [tx["v_buggy"], str(v_buggy), tx["v_buggy_d"]],
                    [tx["v_rate"], pct(video_result.get("bug_rate", 0)), tx["v_rate_d"]],
                    [
                        tx["v_dur"],
                        f"{video_result.get('duration', 0):.1f}s / {video_result.get('fps', 0):.1f} FPS",
                        tx["v_dur_d"],
                    ],
                ],
                [48 * mm, 38 * mm, 83 * mm],
                header_color="#7c3aed",
                body_color="#f5f3ff",
            )
        )

        video_class_counts = {
            cls: int((video_result.get("class_distribution") or {}).get(cls, 0) or 0)
            for cls in BUG_CLASSES
        }
        video_classes = [name for name in BUG_CLASSES if video_class_counts[name] > 0]
        elements.append(Paragraph(tx["dist_video"], h1))
        if video_classes:
            video_dist = [
                [
                    tx["th_type"],
                    tx["th_occ_video"],
                    tx["th_share"],
                    tx["th_severity"],
                    tx["th_short"],
                ]
            ]
            total_video_detections = sum(video_class_counts.values()) or 1
            for name in video_classes:
                guide = guides[name]
                video_dist.append(
                    [
                        Paragraph(esc(guide["title"]), small),
                        str(video_class_counts[name]),
                        f"{video_class_counts[name] / total_video_detections * 100:.1f}%",
                        guide["priority"],
                        Paragraph(esc(guide["description"]), small),
                    ]
                )
            elements.append(
                make_table(
                    video_dist,
                    [35 * mm, 25 * mm, 20 * mm, 20 * mm, 69 * mm],
                    header_color="#7c3aed",
                    body_color="#f5f3ff",
                    font_size=7.2,
                )
            )
            elements.append(Paragraph(tx["fix_video"], h1))
            for name in video_classes:
                guide = guides[name]
                elements.append(
                    Paragraph(
                        f"<b>{esc(guide['title'])}</b> — {tx['priority_word']} {esc(guide['priority'])}",
                        h2,
                    )
                )
                elements.append(
                    Paragraph(
                        f"<b>{tx['checks_label']}</b> {esc(guide['checks'])}<br/><b>{tx['fix_label']}</b> {esc(guide['fix'])}",
                        normal,
                    )
                )
        else:
            elements.append(Paragraph(tx["no_video_bugs"], normal))

        buggy_frames = [frame for frame in video_result.get("frames", []) if frame.get("has_bug")]
        if buggy_frames:
            elements.append(Paragraph(tx["timeline"], h2))
            rows = [
                [
                    tx["th_frame"],
                    tx["th_time"],
                    tx["th_detections"],
                    tx["th_types"],
                    tx["th_action"],
                ]
            ]
            for frame in buggy_frames[:60]:
                types = ", ".join(
                    guides.get(d.get("class_name"), {}).get(
                        "title", d.get("class_name", tx["unknown"]).replace("_", " ")
                    )
                    for d in frame.get("detections", [])
                )
                rows.append(
                    [
                        str(frame.get("frame", 0)),
                        f"{frame.get('timestamp', 0):.2f}s",
                        str(frame.get("num_detections", 0)),
                        Paragraph(esc(types), small),
                        tx["capture_action"],
                    ]
                )
            elements.append(
                make_table(
                    rows,
                    [16 * mm, 21 * mm, 20 * mm, 58 * mm, 54 * mm],
                    header_color="#7c3aed",
                    body_color="#f5f3ff",
                    font_size=7,
                )
            )

    elements.append(PageBreak())
    elements.append(Paragraph(tx["tech_details"], h1))
    buggy_predictions = [p for p in predictions if p.get("has_bug")]
    if not buggy_predictions:
        elements.append(Paragraph(tx["no_image_det"], normal))
    else:
        for index, prediction in enumerate(buggy_predictions[:50], 1):
            filename = esc(prediction.get("filename", tx["unknown_file"]))
            width = prediction.get("image_width") or "?"
            height = prediction.get("image_height") or "?"
            elements.append(
                Paragraph(
                    tx["det_line"].format(
                        index=index,
                        filename=filename,
                        n=prediction.get("num_detections", 0),
                        width=width,
                        height=height,
                    ),
                    bug,
                )
            )
            rows = [[tx["th_type"], tx["th_conf"], tx["th_bbox"], tx["th_reading"]]]
            for detection in prediction.get("detections", []):
                name = detection.get("class_name", "unknown")
                box = detection.get("bbox_xyxy", [])
                confidence = float(detection.get("confidence", 0) or 0)
                if len(box) == 4 and width != "?" and height != "?":
                    x1, y1, x2, y2 = box
                    area = max(0, x2 - x1) * max(0, y2 - y1)
                    area_ratio = (
                        area / (float(width) * float(height)) * 100
                        if float(width) * float(height)
                        else 0
                    )
                    location = f"x1={x1:.0f}, y1={y1:.0f}, x2={x2:.0f}, y2={y2:.0f} ({area_ratio:.1f}% {tx['image_pct']})"
                else:
                    location = str(box)
                confidence_note = (
                    tx["conf_high"]
                    if confidence >= 0.7
                    else tx["conf_mid"]
                    if confidence >= 0.4
                    else tx["conf_low"]
                )
                rows.append(
                    [
                        Paragraph(
                            esc(guides.get(name, {}).get("title", name.replace("_", " "))), small
                        ),
                        f"{confidence * 100:.1f}% ({confidence_note})",
                        Paragraph(esc(location), small),
                        Paragraph(esc(guides.get(name, {}).get("fix", tx["default_fix"])), small),
                    ]
                )
            elements.append(
                make_table(
                    rows,
                    [35 * mm, 34 * mm, 48 * mm, 52 * mm],
                    header_color="#b91c1c",
                    body_color="#fff7f7",
                    font_size=7,
                )
            )
            elements.append(Spacer(1, 5))

    # ── Separate remediation plans ─────────────────────────
    def remediation(rate, medium):
        if rate > 50:
            return tx["sev_critical"], tx["rem_critical"].format(medium=medium)
        if rate > 20:
            return tx["sev_high"], tx["rem_high"].format(medium=medium)
        if rate > 0:
            return tx["sev_moderate"], tx["rem_moderate"].format(medium=medium)
        return tx["sev_none"], tx["rem_none"].format(medium=medium)

    image_priority, image_action = remediation(bug_rate, tx["medium_image"])
    elements.append(Paragraph(tx["plan_image"], h1))
    elements.append(
        make_table(
            [
                [tx["r_image_rate"], f"{bug_rate:.1f}%"],
                [tx["r_image_priority"], image_priority],
                [tx["r_action"], Paragraph(esc(image_action), normal)],
                [tx["r_validation"], tx["r_image_validation"]],
            ],
            [42 * mm, 127 * mm],
            header_color="#0f766e",
            body_color="#f0fdfa",
            font_size=8,
        )
    )

    if video_result and video_result.get("analyzed_frames", 0) > 0:
        video_rate = float(video_result.get("bug_rate", 0)) * 100
        video_priority, video_action = remediation(video_rate, tx["medium_video"])
        elements.append(Paragraph(tx["plan_video"], h1))
        elements.append(
            make_table(
                [
                    [tx["r_video_rate"], f"{video_rate:.1f}%"],
                    [tx["r_video_priority"], video_priority],
                    [tx["r_action"], Paragraph(esc(video_action), normal)],
                    [tx["r_validation"], tx["r_video_validation"]],
                ],
                [42 * mm, 127 * mm],
                header_color="#7c3aed",
                body_color="#f5f3ff",
                font_size=8,
            )
        )
    else:
        elements.append(Paragraph(tx["video_none_h"], h1))
        elements.append(Paragraph(tx["video_none"], normal))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(tx["limits"], note))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
