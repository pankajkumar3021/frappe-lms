# Copyright (c) 2026, FOSS United and Contributors
# For license information, please see license.txt

"""Online sign-up registration. The option lists live here once; the Student
Registration DocType's Select options must equal them (see its test)."""

CLASSES = (
	*(f"Class {number}" for number in range(1, 11)),
	"Class 11 PCM",
	"Class 11 PCB",
	"Class 12 PCM",
	"Class 12 PCB",
)
CITIES = ("Delhi", "Noida", "Muzaffarpur", "Motipur")
FOLLOW_UP_STATUSES = ("New", "Contacted", "Joined", "Not interested")
