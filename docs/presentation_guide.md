# BugSight QA - Presentation Guide

## Elevator Pitch

BugSight QA is an AI-assisted QA tool that detects visual bugs in game
screenshots. Using a YOLOv8 model, it identifies floating objects with
99.5% mAP. QA teams upload screenshots through a web dashboard and get
instant bug detection with bounding boxes and confidence scores.

## Results
   Metric    | Value  |
 |-----------|--------|
 | mAP50     | 99.5%  |
 | Precision | 99.87% |
 | Recall    | 100%   |

## Demo Script

1. Start the stack: docker compose up
2. Open http://localhost:8080
3. Upload a buggy screenshot - red bounding box appears
4. Show stats panel and metrics gauges