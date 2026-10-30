"""PDF reports for BugSight QA.

Images and videos are reported separately and never mixed in one statistic:

- images: summary page (verdict, key figures, model and threshold, charts),
  one evidence card per image with a bug (annotated thumbnail, defects with a
  computed severity and the recommended fix), a guide per detected defect
  type, a remediation plan and an appendix listing every analysed image;
- video: file details, per-type figures, consecutive problematic frames
  grouped into incidents, and a remediation plan.
"""

from __future__ import annotations

import html
import io
import math
import os
from collections import Counter
from datetime import datetime

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

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
        "doc_title_all": "BugSight QA - Rapport détaillé",
        "doc_title_image": "BugSight QA - Rapport images",
        "doc_title_video": "BugSight QA - Rapport vidéo",
        "title_all": "BugSight QA — Rapport de scan détaillé",
        "title_image": "BugSight QA — Rapport d'analyse des images",
        "title_video": "BugSight QA — Rapport d'analyse vidéo",
        "scope_all": "Analyses d'images et une analyse vidéo, présentées dans des parties séparées (aucun chiffre ne mélange images et vidéo).",
        "scope_image": "Analyses d'images uniquement (100 dernières).",
        "scope_video": "Une analyse vidéo uniquement (sans les images).",
        "page": "Page",
        "m_report_id": "N° de rapport",
        "m_generated": "Généré le",
        "m_user": "Testeur",
        "m_model": "Modèle",
        "m_threshold": "Seuil de confiance",
        "m_scope": "Périmètre",
        "model_line": "{name} — mAP50 {map50}, précision {precision}, rappel {recall} (jeu de validation)",
        "unknown": "non enregistré",
        "unknown_file": "fichier inconnu",
        "image_summary": "Synthèse des analyses d'images",
        "no_images": "Aucune analyse d'image n'est enregistrée pour ce compte.",
        "verdict_clean": "Aucun défaut détecté sur les {total} image(s) analysée(s).",
        "verdict_bugs": "{buggy} image(s) sur {total} contiennent {defects} défaut(s) — sévérité : {levels}.",
        "th_indicator": "Indicateur",
        "th_result": "Résultat",
        "th_interp": "Interprétation",
        "row_total": "Images analysées",
        "row_total_d": "Nombre d'images incluses dans ce rapport.",
        "row_buggy": "Images avec défaut",
        "row_buggy_d": "Images nécessitant une vérification QA.",
        "row_clean": "Images propres",
        "row_clean_d": "Aucune détection retenue par le modèle.",
        "row_rate": "Taux d'anomalie",
        "row_rate_d": "Part des images contenant au moins un défaut.",
        "row_defects": "Défauts détectés",
        "row_defects_d": "Nombre total de défauts, toutes images confondues.",
        "row_mean_conf": "Confiance moyenne",
        "row_mean_conf_d": "Moyenne des scores de confiance des défauts détectés.",
        "row_period": "Période",
        "chart_classes": "Défauts par type",
        "chart_conf": "Défauts par niveau de confiance",
        "chart_severity": "Défauts par sévérité",
        "band_high": "≥ 70 % (forte)",
        "band_mid": "40–70 % (à confirmer)",
        "band_low": "< 40 % (faible)",
        "lvl_critical": "Critique",
        "lvl_high": "Élevée",
        "lvl_medium": "Moyenne",
        "lvl_low": "Faible",
        "triage_note": "Le taux de détection est un indicateur de triage et ne constitue pas à lui seul une preuve définitive du bug. Les résultats doivent être confirmés par une revue humaine, en particulier pour les scores de confiance faibles.",
        "cards_h": "Fiches de bug",
        "cards_intro": "Une fiche par image contenant au moins un défaut, de la plus grave à la moins grave. Les numéros sur la capture correspondent aux lignes du tableau. Cochez le statut après vérification.",
        "cards_more": "{n} autre(s) image(s) avec défaut ne sont pas détaillées ici ; elles figurent dans l'annexe.",
        "card_title": "Fiche {index} — {filename}",
        "no_thumbnail": "Capture non disponible (analyse antérieure à l'enregistrement des miniatures).",
        "c_id": "Analyse",
        "c_date": "Date",
        "c_resolution": "Résolution",
        "c_defects": "Défauts",
        "c_worst": "Sévérité max",
        "c_threshold": "Seuil utilisé",
        "c_status": "Statut",
        "c_status_boxes": "☐ Confirmé   ☐ Faux positif   ☐ Corrigé",
        "th_type": "Type",
        "th_conf": "Confiance",
        "th_area": "Zone",
        "th_severity": "Sévérité",
        "th_fix": "Correction recommandée",
        "conf_high": "forte",
        "conf_mid": "à confirmer",
        "conf_low": "faible",
        "default_fix": "Vérifier la scène et le pipeline de rendu.",
        "guide_images": "Guide de diagnostic et de résolution par type de défaut",
        "priority_word": "priorité",
        "occurrences": "occurrence(s)",
        "g_description": "Description",
        "g_impact": "Impact probable",
        "g_checks": "Vérifications QA",
        "g_fix": "Méthode de résolution",
        "annex_h": "Annexe — toutes les images analysées",
        "th_file": "Fichier",
        "th_date": "Date (UTC)",
        "th_outcome": "Résultat",
        "th_defects": "Défauts",
        "th_conf_max": "Conf. max",
        "outcome_bug": "Défaut",
        "outcome_clean": "Propre",
        "video_results": "Résultats de l'analyse vidéo",
        "video_note": "Cette partie est indépendante des résultats image. Les taux, frames et recommandations ci-dessous concernent uniquement la vidéo analysée.",
        "video_h": "Fiche vidéo",
        "v_verdict_clean": "Aucun défaut détecté dans les {frames} frames analysées.",
        "v_verdict_bugs": "{n} incident(s) détecté(s), sur {share} % de la durée de la vidéo — sévérité maximale : {level}.",
        "v_covered": "Durée concernée",
        "of_duration": "de la durée",
        "timeline_h": "Chronologie des défauts",
        "timeline_intro": "Chaque ligne est un type de défaut ; une marque colorée indique une frame analysée où il est détecté.",
        "incident_cards_h": "Fiches d'incident",
        "incident_title": "Incident {number} — {start} s → {end} s",
        "no_keyframes": "Images clés non disponibles (analyse antérieure à leur enregistrement) : utilisez les timestamps pour retrouver les passages.",
        "no_keyframe": "Image clé non disponible.",
        "kf_at": "Image clé",
        "cards_more_video": "{n} autre(s) incident(s) ne sont pas détaillés ici ; ils figurent dans le tableau des incidents.",
        "v_file": "Fichier",
        "v_total": "Frames dans la vidéo",
        "v_analyzed": "Frames analysées",
        "v_analyzed_d": "échantillon réparti sur toute la vidéo (une frame toutes les {interval} s environ).",
        "v_buggy": "Frames avec bug",
        "v_dur": "Durée / FPS",
        "dist_video": "Défauts par type — vidéo",
        "th_frames": "Frames",
        "th_share_frames": "% analysées",
        "th_priority": "Priorité",
        "no_video_bugs": "Aucun défaut n'a été détecté dans cette vidéo.",
        "incidents_h": "Incidents",
        "incidents_intro": "Les frames problématiques consécutives sont regroupées en incidents : chaque ligne correspond à un passage de la vidéo à revoir.",
        "incidents_more": "{n} autre(s) incident(s) non affiché(s).",
        "th_window": "Passage",
        "th_types": "Types détectés",
        "th_action": "Action recommandée",
        "max_word": "max",
        "incident_action": "Ouvrir la vidéo à {time} s, capturer la frame et reproduire la scène.",
        "fix_video": "Méthodes de résolution — vidéo",
        "checks_label": "Vérifications :",
        "fix_label": "Résolution :",
        "sev_none": "Aucune anomalie détectée",
        "medium_image": "image",
        "medium_video": "vidéo",
        "rem_critical": "Bloquer la validation {medium}, isoler les classes dominantes et lancer une investigation du pipeline de rendu avant toute release.",
        "rem_high": "Créer des tickets {medium} par type de défaut, commencer par les classes dominantes et ajouter une reproduction minimale pour chaque anomalie.",
        "rem_moderate": "Revoir manuellement les détections {medium}, corriger les défauts confirmés et ajouter une campagne de non-régression.",
        "rem_none": "Conserver les paramètres de scan {medium} et lancer une nouvelle campagne sur des scènes ou configurations différentes.",
        "plan_image": "Plan de remédiation — images",
        "r_image_rate": "Taux image",
        "r_image_priority": "Priorité image",
        "r_action": "Action immédiate",
        "r_validation": "Validation",
        "r_image_validation": "Relancer les mêmes images après correction et comparer le nombre de détections, la confiance et les zones détectées.",
        "plan_video": "Plan de remédiation — vidéo",
        "r_video_rate": "Taux vidéo",
        "r_video_priority": "Priorité vidéo",
        "r_video_validation": "Relancer la vidéo après correction et comparer les incidents, les timestamps et la répartition des types.",
        "video_none_h": "Résultats vidéo",
        "video_none": "Aucune analyse vidéo n'est incluse dans ce rapport.",
        "method_h": "Méthode et limites",
        "method_severity": "<b>Calcul de la sévérité.</b> Chaque défaut reçoit des points selon son type (3 pour texture manquante, texture corrompue et z-fighting ; 2 pour les autres), +1 si la confiance est d'au moins 70 %, −1 si elle est inférieure à 40 %, et +1 s'il couvre au moins 10 % de l'image. Total : 5 et plus = critique, 4 = élevée, 3 = moyenne, 2 et moins = faible.",
        "limits": "Limites du rapport : la confiance du modèle mesure la probabilité de la classe prédite, mais ne remplace pas la reproduction du défaut dans le jeu. Les procédures proposées sont des pistes de diagnostic QA et doivent être adaptées au moteur, au shader et à la plateforme ciblée.",
    },
    "en": {
        "doc_title_all": "BugSight QA - Detailed report",
        "doc_title_image": "BugSight QA - Image report",
        "doc_title_video": "BugSight QA - Video report",
        "title_all": "BugSight QA — Detailed scan report",
        "title_image": "BugSight QA — Image analysis report",
        "title_video": "BugSight QA — Video analysis report",
        "scope_all": "Image analyses and one video analysis, in separate parts (no figure mixes images and video).",
        "scope_image": "Image analyses only (latest 100).",
        "scope_video": "One video analysis only (no images).",
        "page": "Page",
        "m_report_id": "Report no.",
        "m_generated": "Generated on",
        "m_user": "Tester",
        "m_model": "Model",
        "m_threshold": "Confidence threshold",
        "m_scope": "Scope",
        "model_line": "{name} — mAP50 {map50}, precision {precision}, recall {recall} (validation set)",
        "unknown": "not recorded",
        "unknown_file": "unknown file",
        "image_summary": "Image analysis summary",
        "no_images": "No image analysis is stored for this account.",
        "verdict_clean": "No defect detected in the {total} analyzed image(s).",
        "verdict_bugs": "{buggy} of {total} image(s) contain {defects} defect(s) — severity: {levels}.",
        "th_indicator": "Indicator",
        "th_result": "Result",
        "th_interp": "Interpretation",
        "row_total": "Images analyzed",
        "row_total_d": "Number of images included in this report.",
        "row_buggy": "Images with defects",
        "row_buggy_d": "Images that need a QA check.",
        "row_clean": "Clean images",
        "row_clean_d": "No detection retained by the model.",
        "row_rate": "Anomaly rate",
        "row_rate_d": "Share of images containing at least one defect.",
        "row_defects": "Defects detected",
        "row_defects_d": "Total number of defects across all images.",
        "row_mean_conf": "Mean confidence",
        "row_mean_conf_d": "Average confidence score of the detected defects.",
        "row_period": "Period",
        "chart_classes": "Defects by type",
        "chart_conf": "Defects by confidence level",
        "chart_severity": "Defects by severity",
        "band_high": "≥ 70% (strong)",
        "band_mid": "40–70% (to confirm)",
        "band_low": "< 40% (weak)",
        "lvl_critical": "Critical",
        "lvl_high": "High",
        "lvl_medium": "Medium",
        "lvl_low": "Low",
        "triage_note": "The detection rate is a triage indicator and is not definitive proof of a bug on its own. Results must be confirmed by a human review, especially for low confidence scores.",
        "cards_h": "Bug cards",
        "cards_intro": "One card per image with at least one defect, most severe first. The numbers on the capture match the table rows. Tick the status after review.",
        "cards_more": "{n} more image(s) with defects are not detailed here; they are listed in the appendix.",
        "card_title": "Card {index} — {filename}",
        "no_thumbnail": "Capture not available (analysis made before thumbnails were stored).",
        "c_id": "Analysis",
        "c_date": "Date",
        "c_resolution": "Resolution",
        "c_defects": "Defects",
        "c_worst": "Max severity",
        "c_threshold": "Threshold used",
        "c_status": "Status",
        "c_status_boxes": "☐ Confirmed   ☐ False positive   ☐ Fixed",
        "th_type": "Type",
        "th_conf": "Confidence",
        "th_area": "Area",
        "th_severity": "Severity",
        "th_fix": "Recommended fix",
        "conf_high": "strong",
        "conf_mid": "to confirm",
        "conf_low": "weak",
        "default_fix": "Check the scene and the rendering pipeline.",
        "guide_images": "Diagnosis and resolution guide by defect type",
        "priority_word": "priority",
        "occurrences": "occurrence(s)",
        "g_description": "Description",
        "g_impact": "Likely impact",
        "g_checks": "QA checks",
        "g_fix": "Resolution method",
        "annex_h": "Appendix — every analyzed image",
        "th_file": "File",
        "th_date": "Date (UTC)",
        "th_outcome": "Result",
        "th_defects": "Defects",
        "th_conf_max": "Max conf.",
        "outcome_bug": "Defect",
        "outcome_clean": "Clean",
        "video_results": "Video analysis results",
        "video_note": "This part is independent from the image results. The rates, frames and recommendations below only concern the analyzed video.",
        "video_h": "Video details",
        "v_verdict_clean": "No defect detected in the {frames} analyzed frames.",
        "v_verdict_bugs": "{n} incident(s) detected, over {share}% of the video's duration — highest severity: {level}.",
        "v_covered": "Duration affected",
        "of_duration": "of the duration",
        "timeline_h": "Defect timeline",
        "timeline_intro": "Each row is a defect type; a coloured mark shows an analyzed frame where it was detected.",
        "incident_cards_h": "Incident cards",
        "incident_title": "Incident {number} — {start} s → {end} s",
        "no_keyframes": "Key frames not available (analysis made before they were stored): use the timestamps to find the passages.",
        "no_keyframe": "Key frame not available.",
        "kf_at": "Key frame",
        "cards_more_video": "{n} more incident(s) are not detailed here; they are listed in the incidents table.",
        "v_file": "File",
        "v_total": "Frames in the video",
        "v_analyzed": "Frames analyzed",
        "v_analyzed_d": "sample spread over the whole video (about one frame every {interval} s).",
        "v_buggy": "Frames with bugs",
        "v_dur": "Duration / FPS",
        "dist_video": "Defects by type — video",
        "th_frames": "Frames",
        "th_share_frames": "% analyzed",
        "th_priority": "Priority",
        "no_video_bugs": "No defect was detected in this video.",
        "incidents_h": "Incidents",
        "incidents_intro": "Consecutive problematic frames are grouped into incidents: each row is a part of the video to review.",
        "incidents_more": "{n} more incident(s) not shown.",
        "th_window": "Time range",
        "th_types": "Detected types",
        "th_action": "Recommended action",
        "max_word": "max",
        "incident_action": "Open the video at {time} s, capture the frame and reproduce the scene.",
        "fix_video": "Resolution methods — video",
        "checks_label": "Checks:",
        "fix_label": "Resolution:",
        "sev_none": "No anomaly detected",
        "medium_image": "image",
        "medium_video": "video",
        "rem_critical": "Block the {medium} sign-off, isolate the dominant classes and investigate the rendering pipeline before any release.",
        "rem_high": "Create {medium} tickets per defect type, start with the dominant classes and add a minimal reproduction for each anomaly.",
        "rem_moderate": "Manually review the {medium} detections, fix the confirmed defects and add a regression campaign.",
        "rem_none": "Keep the {medium} scan settings and run a new campaign on different scenes or configurations.",
        "plan_image": "Remediation plan — images",
        "r_image_rate": "Image rate",
        "r_image_priority": "Image priority",
        "r_action": "Immediate action",
        "r_validation": "Validation",
        "r_image_validation": "Re-run the same images after the fix and compare the number of detections, confidence and detected areas.",
        "plan_video": "Remediation plan — video",
        "r_video_rate": "Video rate",
        "r_video_priority": "Video priority",
        "r_video_validation": "Re-run the video after the fix and compare the incidents, timestamps and type distribution.",
        "video_none_h": "Video results",
        "video_none": "No video analysis is included in this report.",
        "method_h": "Method and limits",
        "method_severity": "<b>Severity score.</b> Each defect gets points for its type (3 for missing texture, corrupted texture and z-fighting; 2 for the others), +1 when confidence is at least 70%, −1 when it is below 40%, and +1 when it covers at least 10% of the image. Total: 5 or more = critical, 4 = high, 3 = medium, 2 or less = low.",
        "limits": "Report limits: model confidence measures the probability of the predicted class but does not replace reproducing the defect in the game. The proposed procedures are QA diagnostic leads and must be adapted to the engine, shader and target platform.",
    },
}


# ── Severity ────────────────────────────────────────────────
# Points per class (texture / depth defects are the most visible), then +1 for
# a confident detection (>= 70 %), -1 for a weak one (< 40 %) and +1 when the
# defect covers at least 10 % of the image. Explained in the report itself.
_SEVERITY_BASE = {
    "missing_texture": 3,
    "texture_glitch": 3,
    "z_fighting": 3,
    "screen_tear": 2,
    "uv_stretch": 2,
    "color_corruption": 2,
}
SEVERITY_LEVELS = ("critical", "high", "medium", "low")
_SEVERITY_COLOURS = {
    "critical": "#b91c1c",
    "high": "#ea580c",
    "medium": "#ca8a04",
    "low": "#2563eb",
}
_CONF_HIGH = 0.7
_CONF_LOW = 0.4
_LARGE_AREA_PCT = 10.0
MAX_CARDS = 30
MAX_INCIDENTS = 40
MAX_INCIDENT_CARDS = 12


def severity(class_name: str, confidence: float, area_pct: float | None) -> str:
    """Severity level of one detection: critical, high, medium or low."""
    points = _SEVERITY_BASE.get(class_name, 2)
    if confidence >= _CONF_HIGH:
        points += 1
    elif confidence < _CONF_LOW:
        points -= 1
    if area_pct is not None and area_pct >= _LARGE_AREA_PCT:
        points += 1
    if points >= 5:
        return "critical"
    if points == 4:
        return "high"
    if points == 3:
        return "medium"
    return "low"


def _worst(levels) -> str | None:
    levels = list(levels)
    return min(levels, key=SEVERITY_LEVELS.index) if levels else None


# ── Small helpers ───────────────────────────────────────────

_FONTS: tuple[str, str] | None = None


def _fonts() -> tuple[str, str]:
    """(regular, bold) font names.

    DejaVu Sans (shipped with matplotlib) covers accents, Arabic, Cyrillic...
    so file names are not printed as black squares; Helvetica is the fallback.
    """
    global _FONTS
    if _FONTS is None:
        try:
            import matplotlib

            folder = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
            pdfmetrics.registerFont(TTFont("BSQ", os.path.join(folder, "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("BSQ-Bold", os.path.join(folder, "DejaVuSans-Bold.ttf")))
            for bold, italic in ((0, 0), (0, 1), (1, 0), (1, 1)):
                addMapping("BSQ", bold, italic, "BSQ-Bold" if bold else "BSQ")
            _FONTS = ("BSQ", "BSQ-Bold")
        except Exception:
            _FONTS = ("Helvetica", "Helvetica-Bold")
    return _FONTS


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


def _date(value) -> str:
    """ISO timestamp -> 'YYYY-MM-DD HH:MM' (analyses are stored in UTC)."""
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)[:16]


def make_table(
    data, widths, header_color="#4f46e5", body_color="#f9fafb", font_size=8, header=True
):
    regular, bold = _fonts()
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), regular),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_color)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(body_color)]),
        ]
    else:
        # Label / value tables: first column shaded, no header row.
        commands += [
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor(body_color)),
            ("FONTNAME", (0, 0), (0, -1), bold),
        ]
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    table.setStyle(TableStyle(commands))
    return table


def _bar_chart(labels, values, colour, width=170 * mm, label_width=58 * mm):
    """Horizontal bar chart, first label on top."""
    regular, _ = _fonts()
    row = 14
    drawing = Drawing(width, len(labels) * row + 20)
    chart = HorizontalBarChart()
    chart.x = label_width
    chart.y = 14
    chart.width = width - chart.x - 12 * mm
    chart.height = len(labels) * row
    chart.data = [list(reversed(values))]
    chart.categoryAxis.categoryNames = list(reversed(labels))
    chart.categoryAxis.labels.fontName = regular
    chart.categoryAxis.labels.fontSize = 7.5
    chart.categoryAxis.labels.boxAnchor = "e"
    chart.categoryAxis.labels.dx = -3
    top = max(values) if values else 1
    step = max(1, math.ceil(top / 5))
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = step * (math.ceil(top / step) + 1)
    chart.valueAxis.valueStep = step
    chart.valueAxis.labels.fontName = regular
    chart.valueAxis.labels.fontSize = 7
    chart.bars[0].fillColor = colors.HexColor(colour)
    chart.bars.strokeColor = None
    chart.barLabelFormat = "%d"
    chart.barLabels.fontName = regular
    chart.barLabels.fontSize = 7
    chart.barLabels.nudge = 6
    drawing.add(chart)
    return drawing


def _thumbnail(path, max_width, max_height):
    """Image flowable keeping the aspect ratio, or None when unavailable."""
    if not path or not os.path.exists(path):
        return None
    try:
        width, height = ImageReader(path).getSize()
    except Exception:
        return None
    scale = min(max_width / width, max_height / height)
    return Image(path, width=width * scale, height=height * scale)


def _detection_rows(prediction: dict, guides: dict) -> list[dict]:
    """Detections of one image with their area share and severity."""
    width = prediction.get("image_width") or 0
    height = prediction.get("image_height") or 0
    rows = []
    for detection in prediction.get("detections", []):
        name = detection.get("class_name", "unknown")
        confidence = float(detection.get("confidence", 0) or 0)
        box = detection.get("bbox_xyxy") or []
        area_pct = None
        if len(box) == 4 and width and height:
            x1, y1, x2, y2 = box
            area_pct = max(0, x2 - x1) * max(0, y2 - y1) / (width * height) * 100
        rows.append(
            {
                "class_name": name,
                "title": guides.get(name, {}).get("title", name.replace("_", " ")),
                "confidence": confidence,
                "box": box,
                "area_pct": area_pct,
                "level": severity(name, confidence, area_pct),
            }
        )
    return rows


def _incidents(frames: list[dict], size: tuple | None = None) -> list[dict]:
    """Group consecutive sampled frames that contain a bug into incidents.

    ``size`` is the (width, height) of the frames, used for the area part of
    the severity; without it severity only uses the type and the confidence.
    """
    width, height = size or (None, None)
    incidents = []
    current = None
    for frame in sorted(frames, key=lambda f: f.get("frame", 0)):
        if not frame.get("has_bug"):
            if current:
                incidents.append(current)
                current = None
            continue
        timestamp = float(frame.get("timestamp", 0) or 0)
        if current is None:
            current = {
                "start": timestamp,
                "end": timestamp,
                "frames": 0,
                "classes": {},
                "level": None,
            }
        current["end"] = timestamp
        current["frames"] += 1
        for detection in frame.get("detections", []):
            name = detection.get("class_name", "unknown")
            confidence = float(detection.get("confidence", 0) or 0)
            current["classes"][name] = max(current["classes"].get(name, 0), confidence)
            box = detection.get("bbox_xyxy") or []
            area = None
            if len(box) == 4 and width and height:
                area = max(0, box[2] - box[0]) * max(0, box[3] - box[1]) / (width * height) * 100
            level = severity(name, confidence, area)
            current["level"] = _worst([lv for lv in (current["level"], level) if lv])
    if current:
        incidents.append(current)
    return incidents


# Same colours as the boxes drawn on thumbnails (src/api/app.py, in RGB here).
_CLASS_HEX = {
    "missing_texture": "#ff00cb",
    "texture_glitch": "#ffa500",
    "z_fighting": "#00c8ff",
    "screen_tear": "#3c78ff",
    "uv_stretch": "#3cc85a",
    "color_corruption": "#f05050",
}


def _timeline(frames, names, labels, span, interval, width=170 * mm):
    """One horizontal track per defect type; a mark wherever a sampled frame has it."""
    regular, _ = _fonts()
    row, label_width, axis = 13, 48 * mm, 16
    left, right = label_width, width - 4 * mm
    height = len(names) * row + axis + 4
    drawing = Drawing(width, height)
    span = max(span, 0.01)
    mark = max(1.5, interval / span * (right - left))
    for index, (name, label) in enumerate(zip(names, labels, strict=True)):
        y = height - (index + 1) * row
        drawing.add(String(left - 4, y + 3, label, fontName=regular, fontSize=7, textAnchor="end"))
        drawing.add(
            Rect(
                left,
                y,
                right - left,
                row - 4,
                fillColor=colors.HexColor("#f1f5f9"),
                strokeColor=None,
            )
        )
        colour = colors.HexColor(_CLASS_HEX.get(name, "#64748b"))
        for frame in frames:
            if any(d.get("class_name") == name for d in frame.get("detections", [])):
                x = left + float(frame.get("timestamp", 0) or 0) / span * (right - left)
                drawing.add(
                    Rect(x, y, min(mark, right - x), row - 4, fillColor=colour, strokeColor=None)
                )
    base = axis - 4
    drawing.add(
        Line(left, base, right, base, strokeColor=colors.HexColor("#94a3b8"), strokeWidth=0.5)
    )
    for step in range(6):
        x = left + step / 5 * (right - left)
        drawing.add(
            Line(x, base, x, base - 3, strokeColor=colors.HexColor("#94a3b8"), strokeWidth=0.5)
        )
        drawing.add(
            String(
                x, 0, f"{span * step / 5:.1f}s", fontName=regular, fontSize=6.5, textAnchor="middle"
            )
        )
    return drawing


class _Styles:
    def __init__(self) -> None:
        regular, bold = _fonts()
        self.title = ParagraphStyle(
            "BSQTitle",
            fontName=bold,
            fontSize=19,
            leading=24,
            textColor=colors.HexColor("#4338ca"),
            spaceAfter=6,
        )
        self.h1 = ParagraphStyle(
            "BSQH1",
            fontName=bold,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1f2937"),
            spaceBefore=10,
            spaceAfter=6,
        )
        self.h2 = ParagraphStyle(
            "BSQH2",
            fontName=bold,
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#374151"),
            spaceBefore=7,
            spaceAfter=4,
        )
        self.normal = ParagraphStyle(
            "BSQNormal",
            fontName=regular,
            fontSize=8.6,
            leading=11.5,
            textColor=colors.HexColor("#4b5563"),
        )
        self.small = ParagraphStyle("BSQSmall", parent=self.normal, fontSize=7.3, leading=9.6)
        self.card = ParagraphStyle(
            "BSQCard", parent=self.h2, textColor=colors.HexColor("#b91c1c"), spaceBefore=4
        )
        self.note = ParagraphStyle(
            "BSQNote",
            parent=self.normal,
            backColor=colors.HexColor("#eff6ff"),
            borderColor=colors.HexColor("#bfdbfe"),
            borderWidth=0.5,
            borderPadding=6,
            leftIndent=6,
            rightIndent=6,
            spaceBefore=8,
            spaceAfter=10,
        )

    def verdict(self, colour: str) -> ParagraphStyle:
        return ParagraphStyle(
            f"BSQVerdict{colour}",
            parent=self.normal,
            fontName=_fonts()[1],
            fontSize=10.5,
            leading=14,
            textColor=colors.white,
            backColor=colors.HexColor(colour),
            borderPadding=8,
            leftIndent=8,
            rightIndent=8,
            spaceBefore=8,
            spaceAfter=12,
        )


def _level_text(level: str | None, tx: dict, st: _Styles):
    if level is None:
        return "-"
    return Paragraph(
        f'<font color="{_SEVERITY_COLOURS[level]}"><b>{esc(tx["lvl_" + level])}</b></font>',
        st.small,
    )


def _remediation(worst: str | None, medium: str, tx: dict) -> tuple[str, str]:
    """(priority, action) driven by the worst computed severity, so the plan agrees with the cards."""
    if worst is None:
        return tx["sev_none"], tx["rem_none"].format(medium=medium)
    template = {"critical": "rem_critical", "high": "rem_high"}.get(worst, "rem_moderate")
    return tx["lvl_" + worst], tx[template].format(medium=medium)


def _thresholds(values) -> str | None:
    values = sorted({round(float(v), 2) for v in values if v is not None})
    if not values:
        return None
    return f"{values[0]:.2f}" if len(values) == 1 else f"{values[0]:.2f} – {values[-1]:.2f}"


def _model_line(model_info: dict | None, tx: dict) -> str:
    if not model_info:
        return "-"
    return tx["model_line"].format(
        name=esc(model_info.get("name", "-")),
        map50=pct(model_info.get("mAP50", 0)),
        precision=pct(model_info.get("precision", 0)),
        recall=pct(model_info.get("recall", 0)),
    )


# ── Image part ──────────────────────────────────────────────


def _image_elements(predictions, tx, guides, st, model_info) -> list:
    elements: list = []
    total = len(predictions)
    buggy_predictions = [p for p in predictions if p.get("has_bug")]
    buggy = len(buggy_predictions)
    bug_rate = buggy / total * 100 if total else 0.0

    rows_by_id = {id(p): _detection_rows(p, guides) for p in predictions}
    all_rows = [row for rows in rows_by_id.values() for row in rows]
    level_counts = Counter(row["level"] for row in all_rows)
    class_counts = Counter(row["class_name"] for row in all_rows)

    # Summary: verdict, then key figures.
    elements.append(Paragraph(tx["image_summary"], st.h1))
    if not total:
        elements.append(Paragraph(tx["no_images"], st.verdict("#475569")))
        return elements
    if not all_rows:
        verdict, colour = tx["verdict_clean"].format(total=total), "#15803d"
    else:
        worst = _worst(level_counts)
        colour = _SEVERITY_COLOURS[worst]
        levels = ", ".join(
            f"{level_counts[level]} {tx['lvl_' + level].lower()}"
            for level in SEVERITY_LEVELS
            if level_counts[level]
        )
        verdict = tx["verdict_bugs"].format(
            buggy=buggy, total=total, defects=len(all_rows), levels=levels
        )
    elements.append(Paragraph(verdict, st.verdict(colour)))

    timestamps = sorted(p["timestamp"] for p in predictions if p.get("timestamp"))
    period = f"{_date(timestamps[0])} → {_date(timestamps[-1])} UTC" if timestamps else "-"
    mean_conf = sum(r["confidence"] for r in all_rows) / len(all_rows) if all_rows else 0
    elements.append(
        make_table(
            [
                [tx["th_indicator"], tx["th_result"], tx["th_interp"]],
                [tx["row_total"], str(total), Paragraph(tx["row_total_d"], st.small)],
                [tx["row_buggy"], str(buggy), Paragraph(tx["row_buggy_d"], st.small)],
                [tx["row_clean"], str(total - buggy), Paragraph(tx["row_clean_d"], st.small)],
                [tx["row_rate"], f"{bug_rate:.1f}%", Paragraph(tx["row_rate_d"], st.small)],
                [tx["row_defects"], str(len(all_rows)), Paragraph(tx["row_defects_d"], st.small)],
                [
                    tx["row_mean_conf"],
                    f"{mean_conf * 100:.1f}%" if all_rows else "-",
                    Paragraph(tx["row_mean_conf_d"], st.small),
                ],
                [tx["row_period"], Paragraph(esc(period), st.small), ""],
            ],
            [44 * mm, 40 * mm, 85 * mm],
        )
    )

    if all_rows:
        detected = [name for name in BUG_CLASSES if class_counts[name]]
        elements.append(Paragraph(tx["chart_classes"], st.h2))
        elements.append(
            _bar_chart(
                [guides[name]["title"] for name in detected],
                [class_counts[name] for name in detected],
                "#dc2626",
            )
        )
        bands = [
            sum(1 for r in all_rows if r["confidence"] >= _CONF_HIGH),
            sum(1 for r in all_rows if _CONF_LOW <= r["confidence"] < _CONF_HIGH),
            sum(1 for r in all_rows if r["confidence"] < _CONF_LOW),
        ]
        # Confidence and severity side by side to keep the summary on one page.
        half = 84 * mm
        pair = Table(
            [
                [Paragraph(tx["chart_conf"], st.h2), Paragraph(tx["chart_severity"], st.h2)],
                [
                    _bar_chart(
                        [tx["band_high"], tx["band_mid"], tx["band_low"]],
                        bands,
                        "#4f46e5",
                        width=half,
                        label_width=33 * mm,
                    ),
                    _bar_chart(
                        [tx["lvl_" + level] for level in SEVERITY_LEVELS],
                        [level_counts[level] for level in SEVERITY_LEVELS],
                        "#ea580c",
                        width=half,
                        label_width=20 * mm,
                    ),
                ],
            ],
            colWidths=[half + 1 * mm, half + 1 * mm],
        )
        pair.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        elements.append(pair)
    elements.append(Paragraph(tx["triage_note"], st.note))

    # Evidence cards, worst images first.
    if buggy_predictions:
        elements.append(PageBreak())
        elements.append(Paragraph(tx["cards_h"], st.h1))
        elements.append(Paragraph(tx["cards_intro"], st.normal))
        ordered = sorted(
            buggy_predictions,
            key=lambda p: (
                SEVERITY_LEVELS.index(_worst(r["level"] for r in rows_by_id[id(p)]) or "low"),
                -len(rows_by_id[id(p)]),
            ),
        )
        for index, prediction in enumerate(ordered[:MAX_CARDS], 1):
            elements.append(_card(index, prediction, rows_by_id[id(prediction)], tx, guides, st))
        if len(ordered) > MAX_CARDS:
            elements.append(Paragraph(tx["cards_more"].format(n=len(ordered) - MAX_CARDS), st.note))

        # One guide per detected defect type (instead of repeating it per image).
        elements.append(Paragraph(tx["guide_images"], st.h1))
        for name in [n for n in BUG_CLASSES if class_counts[n]]:
            guide = guides[name]
            elements.append(
                KeepTogether(
                    [
                        Paragraph(
                            f"{esc(guide['title'])} — {tx['priority_word']} "
                            f"{esc(guide['priority'])} · {class_counts[name]} {tx['occurrences']}",
                            st.h2,
                        ),
                        make_table(
                            [
                                [
                                    tx["g_description"],
                                    Paragraph(esc(guide["description"]), st.small),
                                ],
                                [tx["g_impact"], Paragraph(esc(guide["impact"]), st.small)],
                                [tx["g_checks"], Paragraph(esc(guide["checks"]), st.small)],
                                [tx["g_fix"], Paragraph(esc(guide["fix"]), st.small)],
                            ],
                            [37 * mm, 132 * mm],
                            body_color="#f1f5f9",
                            font_size=7.5,
                            header=False,
                        ),
                    ]
                )
            )

    priority, action = _remediation(_worst(level_counts), tx["medium_image"], tx)
    elements.append(Paragraph(tx["plan_image"], st.h1))
    elements.append(
        make_table(
            [
                [tx["r_image_rate"], f"{bug_rate:.1f}%"],
                [tx["r_image_priority"], priority],
                [tx["r_action"], Paragraph(esc(action), st.normal)],
                [tx["r_validation"], Paragraph(esc(tx["r_image_validation"]), st.normal)],
            ],
            [42 * mm, 127 * mm],
            body_color="#f0fdfa",
            header=False,
        )
    )

    # Appendix: every analysed image, clean ones included (traceability).
    elements.append(PageBreak())
    elements.append(Paragraph(tx["annex_h"], st.h1))
    annex = [
        [
            "#",
            tx["th_file"],
            tx["th_date"],
            tx["th_outcome"],
            tx["th_defects"],
            tx["th_conf_max"],
            tx["th_severity"],
        ]
    ]
    for index, prediction in enumerate(predictions, 1):
        rows = rows_by_id[id(prediction)]
        annex.append(
            [
                str(index),
                Paragraph(esc(prediction.get("filename", tx["unknown_file"])), st.small),
                _date(prediction.get("timestamp")),
                tx["outcome_bug"] if prediction.get("has_bug") else tx["outcome_clean"],
                str(len(rows)),
                f"{max(r['confidence'] for r in rows) * 100:.0f}%" if rows else "-",
                _level_text(_worst(r["level"] for r in rows), tx, st),
            ]
        )
    elements.append(
        make_table(
            annex,
            [8 * mm, 55 * mm, 28 * mm, 20 * mm, 15 * mm, 18 * mm, 25 * mm],
            header_color="#334155",
            body_color="#f8fafc",
            font_size=7,
        )
    )
    return elements


def _card(index, prediction, rows, tx, guides, st):
    """Evidence card of one image: thumbnail, details, defects."""
    width = prediction.get("image_width") or "?"
    height = prediction.get("image_height") or "?"
    thumb = _thumbnail(prediction.get("thumbnail_path"), 84 * mm, 62 * mm) or Paragraph(
        tx["no_thumbnail"], st.small
    )
    threshold = prediction.get("confidence_threshold")
    info = make_table(
        [
            [tx["c_id"], prediction.get("id", "-")],
            [tx["c_date"], f"{_date(prediction.get('timestamp'))} UTC"],
            [tx["c_resolution"], f"{width} × {height}"],
            [tx["c_defects"], str(len(rows))],
            [tx["c_worst"], _level_text(_worst(r["level"] for r in rows), tx, st)],
            [tx["c_threshold"], f"{threshold:.2f}" if threshold is not None else tx["unknown"]],
            [tx["c_status"], Paragraph(tx["c_status_boxes"], st.small)],
        ],
        [26 * mm, 55 * mm],
        body_color="#f8fafc",
        font_size=7.3,
        header=False,
    )
    top = Table([[thumb, info]], colWidths=[88 * mm, 81 * mm])
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    defects = [["#", tx["th_type"], tx["th_conf"], tx["th_area"], tx["th_severity"], tx["th_fix"]]]
    for number, row in enumerate(rows, 1):
        confidence = row["confidence"]
        band = (
            tx["conf_high"]
            if confidence >= _CONF_HIGH
            else tx["conf_mid"]
            if confidence >= _CONF_LOW
            else tx["conf_low"]
        )
        defects.append(
            [
                str(number),
                Paragraph(esc(row["title"]), st.small),
                Paragraph(f"{confidence * 100:.0f}% ({esc(band)})", st.small),
                f"{row['area_pct']:.1f}%" if row["area_pct"] is not None else "-",
                _level_text(row["level"], tx, st),
                Paragraph(
                    esc(guides.get(row["class_name"], {}).get("fix", tx["default_fix"])), st.small
                ),
            ]
        )
    return KeepTogether(
        [
            Paragraph(
                tx["card_title"].format(
                    index=index, filename=esc(prediction.get("filename", tx["unknown_file"]))
                ),
                st.card,
            ),
            top,
            Spacer(1, 4),
            make_table(
                defects,
                [7 * mm, 30 * mm, 27 * mm, 16 * mm, 19 * mm, 70 * mm],
                header_color="#b91c1c",
                body_color="#fff7f7",
                font_size=7,
            ),
            Spacer(1, 10),
        ]
    )


# ── Video part ──────────────────────────────────────────────


def _video_elements(video_result, tx, guides, st) -> list:
    elements: list = [Paragraph(tx["video_results"], st.title)]
    frames = sorted(video_result.get("frames", []) or [], key=lambda f: f.get("frame", 0))
    analyzed = video_result.get("analyzed_frames", 0) or len(frames)
    buggy = video_result.get("buggy_frames", 0)
    duration = float(video_result.get("duration", 0) or 0)
    rate = float(video_result.get("bug_rate", 0) or 0) * 100
    threshold = video_result.get("confidence_threshold")
    interval = duration / analyzed if analyzed and duration else 0
    size = None
    if video_result.get("width") and video_result.get("height"):
        size = (video_result["width"], video_result["height"])
    incidents = _incidents(frames, size)
    keyframes = video_result.get("keyframe_paths") or {}
    keyframe_meta = video_result.get("keyframes") or []
    last = float(frames[-1].get("timestamp", 0) or 0) if frames else 0
    span = max(duration, last + interval)

    # Verdict: share of the video's duration covered by incidents.
    covered = sum(min(span, i["end"] - i["start"] + interval) for i in incidents)
    share = min(100.0, covered / span * 100) if span else 0.0
    if not incidents:
        verdict, colour = tx["v_verdict_clean"].format(frames=analyzed), "#15803d"
    else:
        worst = _worst(i["level"] for i in incidents if i["level"]) or "low"
        colour = _SEVERITY_COLOURS[worst]
        verdict = tx["v_verdict_bugs"].format(
            n=len(incidents), share=f"{share:.0f}", level=tx["lvl_" + worst].lower()
        )
    elements.append(Paragraph(verdict, st.verdict(colour)))
    elements.append(Paragraph(tx["video_note"], st.note))

    elements.append(Paragraph(tx["video_h"], st.h1))
    resolution = f"{size[0]} × {size[1]}" if size else "-"
    elements.append(
        make_table(
            [
                [tx["v_file"], Paragraph(esc(video_result.get("filename") or "-"), st.small)],
                [tx["c_id"], video_result.get("id") or "-"],
                [tx["c_date"], f"{_date(video_result.get('timestamp'))} UTC"],
                [
                    tx["v_dur"],
                    f"{duration:.1f}s · {float(video_result.get('fps', 0) or 0):.1f} FPS · {resolution}",
                ],
                [tx["v_total"], str(video_result.get("total_frames", 0))],
                [
                    tx["v_analyzed"],
                    Paragraph(
                        f"{analyzed} — " + tx["v_analyzed_d"].format(interval=f"{interval:.2f}"),
                        st.small,
                    ),
                ],
                [tx["v_buggy"], f"{buggy} ({rate:.1f}%)"],
                [tx["v_covered"], f"{share:.0f}%"],
                [tx["c_threshold"], f"{threshold:.2f}" if threshold is not None else tx["unknown"]],
            ],
            [44 * mm, 125 * mm],
            body_color="#f5f3ff",
            header=False,
        )
    )

    # Per type: frames touched (not raw box counts, which double-count a defect
    # seen in many frames).
    frames_per_class = Counter()
    max_conf: dict[str, float] = {}
    for frame in frames:
        names = set()
        for detection in frame.get("detections", []):
            name = detection.get("class_name", "")
            names.add(name)
            max_conf[name] = max(max_conf.get(name, 0), float(detection.get("confidence", 0) or 0))
        frames_per_class.update(names)
    if not frames:  # older analyses without per-frame data
        frames_per_class = Counter(
            {k: int(v or 0) for k, v in (video_result.get("class_distribution") or {}).items()}
        )
    detected = [name for name in BUG_CLASSES if frames_per_class[name]]

    if detected and frames:
        elements.append(Paragraph(tx["timeline_h"], st.h1))
        elements.append(Paragraph(tx["timeline_intro"], st.small))
        elements.append(Spacer(1, 4))
        elements.append(
            _timeline(frames, detected, [guides[n]["title"] for n in detected], span, interval)
        )

    elements.append(Paragraph(tx["dist_video"], st.h1))
    if detected:
        table = [
            [
                tx["th_type"],
                tx["th_frames"],
                tx["th_share_frames"],
                tx["th_conf_max"],
                tx["th_priority"],
            ]
        ]
        for name in detected:
            table.append(
                [
                    Paragraph(esc(guides[name]["title"]), st.small),
                    str(frames_per_class[name]),
                    f"{frames_per_class[name] / analyzed * 100:.1f}%" if analyzed else "-",
                    f"{max_conf[name] * 100:.0f}%" if name in max_conf else "-",
                    guides[name]["priority"],
                ]
            )
        elements.append(
            make_table(
                table,
                [52 * mm, 25 * mm, 32 * mm, 30 * mm, 30 * mm],
                header_color="#7c3aed",
                body_color="#f5f3ff",
                font_size=7.5,
            )
        )
    else:
        elements.append(Paragraph(tx["no_video_bugs"], st.normal))

    if incidents:
        elements.append(Paragraph(tx["incidents_h"], st.h1))
        elements.append(Paragraph(tx["incidents_intro"], st.normal))
        rows = [["#", tx["th_window"], tx["th_frames"], tx["th_types"], tx["th_severity"]]]
        for number, incident in enumerate(incidents[:MAX_INCIDENTS], 1):
            rows.append(
                [
                    str(number),
                    f"{incident['start']:.2f}s → {incident['end']:.2f}s",
                    str(incident["frames"]),
                    Paragraph(esc(_incident_types(incident, tx, guides)), st.small),
                    _level_text(incident["level"], tx, st),
                ]
            )
        elements.append(
            make_table(
                rows,
                [8 * mm, 34 * mm, 16 * mm, 86 * mm, 25 * mm],
                header_color="#7c3aed",
                body_color="#f5f3ff",
                font_size=7,
            )
        )
        if len(incidents) > MAX_INCIDENTS:
            elements.append(
                Paragraph(tx["incidents_more"].format(n=len(incidents) - MAX_INCIDENTS), st.note)
            )

        # One card per incident with its key frame (the most confident frame).
        cards = [
            _incident_card(
                number,
                incident,
                keyframes.get(number) or keyframes.get(str(number)),
                keyframe_meta[number - 1] if number - 1 < len(keyframe_meta) else None,
                tx,
                guides,
                st,
            )
            for number, incident in enumerate(incidents[:MAX_INCIDENT_CARDS], 1)
        ]
        elements.append(Paragraph(tx["incident_cards_h"], st.h1))
        if not keyframes:
            elements.append(Paragraph(tx["no_keyframes"], st.note))
        elements += cards
        if len(incidents) > MAX_INCIDENT_CARDS:
            elements.append(
                Paragraph(
                    tx["cards_more_video"].format(n=len(incidents) - MAX_INCIDENT_CARDS), st.note
                )
            )

    if detected:
        elements.append(Paragraph(tx["fix_video"], st.h1))
        for name in detected:
            guide = guides[name]
            elements.append(
                KeepTogether(
                    [
                        Paragraph(
                            f"{esc(guide['title'])} — {tx['priority_word']} {esc(guide['priority'])}",
                            st.h2,
                        ),
                        Paragraph(
                            f"<b>{tx['checks_label']}</b> {esc(guide['checks'])}<br/>"
                            f"<b>{tx['fix_label']}</b> {esc(guide['fix'])}",
                            st.normal,
                        ),
                    ]
                )
            )

    priority, action = _remediation(
        _worst(i["level"] for i in incidents if i["level"]), tx["medium_video"], tx
    )
    elements.append(
        KeepTogether(
            [
                Paragraph(tx["plan_video"], st.h1),
                make_table(
                    [
                        [tx["r_video_rate"], f"{rate:.1f}% · {share:.0f}% {tx['of_duration']}"],
                        [tx["r_video_priority"], priority],
                        [tx["r_action"], Paragraph(esc(action), st.normal)],
                        [tx["r_validation"], Paragraph(esc(tx["r_video_validation"]), st.normal)],
                    ],
                    [42 * mm, 127 * mm],
                    body_color="#f5f3ff",
                    header=False,
                ),
            ]
        )
    )
    return elements


def _incident_types(incident: dict, tx: dict, guides: dict) -> str:
    return ", ".join(
        f"{guides.get(name, {}).get('title', name.replace('_', ' '))} "
        f"({tx['max_word']} {conf * 100:.0f}%)"
        for name, conf in sorted(incident["classes"].items(), key=lambda kv: -kv[1])
    )


def _incident_card(number, incident, keyframe_path, keyframe, tx, guides, st):
    """Incident of a video: key frame and what to do."""
    image = _thumbnail(keyframe_path, 84 * mm, 50 * mm) or Paragraph(tx["no_keyframe"], st.small)
    at = keyframe["timestamp"] if keyframe else incident["start"]
    info = make_table(
        [
            [tx["th_window"], f"{incident['start']:.2f}s → {incident['end']:.2f}s"],
            [tx["th_frames"], str(incident["frames"])],
            [tx["kf_at"], f"{at:.2f}s"],
            [tx["th_severity"], _level_text(incident["level"], tx, st)],
            [tx["th_types"], Paragraph(esc(_incident_types(incident, tx, guides)), st.small)],
            [
                tx["th_action"],
                Paragraph(esc(tx["incident_action"].format(time=f"{at:.2f}")), st.small),
            ],
            [tx["c_status"], Paragraph(tx["c_status_boxes"], st.small)],
        ],
        [34 * mm, 47 * mm],
        body_color="#f5f3ff",
        font_size=7.3,
        header=False,
    )
    top = Table([[image, info]], colWidths=[88 * mm, 81 * mm])
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    title = ParagraphStyle("BSQIncident", parent=st.card, textColor=colors.HexColor("#7c3aed"))
    return KeepTogether(
        [
            Paragraph(
                tx["incident_title"].format(
                    number=number, start=f"{incident['start']:.2f}", end=f"{incident['end']:.2f}"
                ),
                title,
            ),
            top,
            Spacer(1, 10),
        ]
    )


# ── Entry point ─────────────────────────────────────────────


def generate_report(
    predictions: list[dict],
    user_name: str = "QA Tester",
    stats: dict | None = None,
    video_result: dict | None = None,
    lang: str = DEFAULT_LANG,
    *,
    report_type: str = "all",
    model_info: dict | None = None,
    report_id: str | None = None,
) -> bytes:
    """Build the PDF report.

    ``predictions`` are image analyses only (dicts from ``Prediction.to_dict``,
    optionally with a ``thumbnail_path``); anything with ``media_type`` "video"
    is ignored so videos never inflate the image figures. ``report_type`` is
    "all", "image" or "video". ``stats`` is accepted for backward compatibility
    and unused. ``lang`` is "fr" or "en" (anything else falls back to French).
    """
    lang = normalize_lang(lang)
    tx = TEXTS[lang]
    guides = GUIDES[lang]
    st = _Styles()
    regular, _ = _fonts()
    report_type = report_type if report_type in {"all", "image", "video"} else "all"
    images = [p for p in predictions if (p.get("media_type") or "image") == "image"]
    has_video = bool(video_result and video_result.get("analyzed_frames", 0) > 0)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_id = report_id or f"BSQ-{datetime.now():%Y%m%d-%H%M%S}"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=tx["doc_title_" + report_type],
        author="BugSight QA",
    )

    def decorate(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e5e7eb"))
        canvas.line(16 * mm, 12 * mm, A4[0] - 16 * mm, 12 * mm)
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        canvas.drawString(16 * mm, 8 * mm, f"BugSight QA · {report_id}")
        canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"{tx['page']} {document.page}")
        canvas.restoreState()

    thresholds = [p.get("confidence_threshold") for p in images]
    if has_video:
        thresholds.append(video_result.get("confidence_threshold"))
    elements: list = [
        Paragraph(tx["title_" + report_type], st.title),
        make_table(
            [
                [tx["m_report_id"], report_id],
                [tx["m_generated"], generated],
                [tx["m_user"], Paragraph(esc(user_name), st.small)],
                [tx["m_model"], Paragraph(_model_line(model_info, tx), st.small)],
                [tx["m_threshold"], _thresholds(thresholds) or tx["unknown"]],
                [tx["m_scope"], Paragraph(tx["scope_" + report_type], st.small)],
            ],
            [36 * mm, 133 * mm],
            body_color="#eef2ff",
            font_size=7.8,
            header=False,
        ),
    ]

    if report_type in {"all", "image"}:
        elements += _image_elements(images, tx, guides, st, model_info)

    if report_type in {"all", "video"}:
        if has_video:
            if report_type == "all":  # the video part starts on its own page
                elements.append(PageBreak())
            else:
                elements.append(Spacer(1, 10))
            elements += _video_elements(video_result, tx, guides, st)
        else:
            elements.append(Paragraph(tx["video_none_h"], st.h1))
            elements.append(Paragraph(tx["video_none"], st.normal))

    elements.append(Paragraph(tx["method_h"], st.h1))
    elements.append(Paragraph(tx["method_severity"], st.normal))
    elements.append(Paragraph(tx["limits"], st.note))

    doc.build(elements, onFirstPage=decorate, onLaterPages=decorate)
    buffer.seek(0)
    return buffer.getvalue()
