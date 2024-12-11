def update_rating_table(self):
        """Update the rating evaluation table with the measured values for each metric."""
        print("\nEvaluating Cracks:")
        if not self.rating_table_widget:
            return

        # Calculate the perimeter length (CSD)
        perimeter_length = sum(
            math.hypot(self.perimeter_spline[i + 1].x() - self.perimeter_spline[i].x(),
                    self.perimeter_spline[i + 1].y() - self.perimeter_spline[i].y())
            for i in range(len(self.perimeter_spline) - 1)
        )
        perimeter_length += math.hypot(
            self.perimeter_spline[-1].x() - self.perimeter_spline[0].x(),
            self.perimeter_spline[-1].y() - self.perimeter_spline[0].y()
        )
        csd = perimeter_length / math.pi if perimeter_length > 0 else 1  # Prevent division by zero

        # Calculate total crack length and length percentages
        total_crack_length = 0
        crack_lengths = []
        external_crack_lengths = []

        for crack, color in self.cracks:
            crack_length = sum(math.hypot(crack[i + 1].x() - crack[i].x(), crack[i + 1].y() - crack[i].y()) for i in range(len(crack) - 1))
            total_crack_length += crack_length
            crack_lengths.append((crack_length, color))
            if color == Qt.GlobalColor.yellow:  # External cracks
                external_crack_lengths.append(crack_length)

        
        ## Rating 1 conditions
            # Metric 1: Total Crack Length (% of CSD) below 1 x CSD
        combined_length_all_cracks = (total_crack_length / csd) * 100 if csd > 0 else 0
        all_cracks_combined_below_CSD = combined_length_all_cracks <= csd
        self.rating_table_widget.setItem(0, 1, QTableWidgetItem(f"{combined_length_all_cracks:.2f}%"))

            # Metric 2: # Cracks < 25% CSD
        cracks_below_25_percent = sum(1 for length, _ in crack_lengths if (length / csd) * 100 < 25)
        all_cracks_below_25_percent = all((length / csd) * 100 < 25 for length, _ in crack_lengths)
        self.rating_table_widget.setItem(1, 1, QTableWidgetItem(str(cracks_below_25_percent)))

            # Metric 3: All external cracks should be < 10% CSD
        all_external_cracks_below_10_percent = all((length / csd) * 100 < 10 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)

        ## Rating 2 conditions
            # Metric 1: # Cracks < 50% CSD
        num_cracks_below_50_percent = sum(1 for length, _ in crack_lengths if (length / csd) * 100 < 50)
        all_cracks_below_50_percent = all((length / csd) * 100 < 50 for length, _ in crack_lengths)
        self.rating_table_widget.setItem(2, 1, QTableWidgetItem(str(num_cracks_below_50_percent)))

            # Metric 2: Total Crack Length (% of CSD) below 2 x CSD
        all_cracks_combined_below_2xCSD = combined_length_all_cracks <= (2 * csd)

            # Metric 3: All external cracks should be < 25% CSD
        all_external_cracks_below_25_percent = all((length / csd) * 100 < 25 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)

        ## Rating 3 conditions
            # Metric 1: Two or less Internal Cracks 50-80% CSD
        num_internal_cracks_50_80_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and 50 <= (length / csd) * 100 <= 80)
        two_or_less_50_80_internal_cracks = num_internal_cracks_50_80_percent <= 2
        self.rating_table_widget.setItem(5, 1, QTableWidgetItem(str(num_internal_cracks_50_80_percent)))

            # Metric 2: Total Crack Length (% of CSD) below 3 x csd
        all_cracks_combined_below_3xCSD = combined_length_all_cracks <= (3 * csd)

            # Metric 3: All external cracks sholud be < 50% CSD
        all_external_cracks_below_50_percent = all((length / csd) * 100 < 50 for length, color in crack_lengths if color == Qt.GlobalColor.yellow)

        ## Rating 4 conditions
            # Metric 1: Total Crack Length (% of CSD) above 3 x csd
        all_cracks_combined_above_3xCSD = combined_length_all_cracks > (3 * csd)

            # Metric 2: One Internal Crack > 80% CSD
        num_internal_cracks_above_80_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 80)
        at_least_one_internal_crack_above_80_percent = num_internal_cracks_above_80_percent > 0

            # Metric 3: 3 or more internal cracks > 50% CSD
        num_internal_cracks_above_50_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 50)
        three_or_more_internal_cracks_above_50_percent = num_internal_cracks_above_50_percent >= 3

            # Metric 4: Any external crack > 50% CSD
        num_external_cracks_above_50_percent = sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.yellow and (length / csd) * 100 > 50)
        at_least_one_external_crack_above_80_percent = num_external_cracks_above_50_percent > 0

        # Metric 2: # Internal Cracks (color = blue)
        internal_cracks_count = sum(1 for _, color in crack_lengths if color == Qt.GlobalColor.blue)
        self.rating_table_widget.setItem(3, 1, QTableWidgetItem(str(internal_cracks_count)))

        # Metric 5: # External Cracks (color = yellow)
        external_cracks_count = sum(1 for _, color in crack_lengths if color == Qt.GlobalColor.yellow)
        self.rating_table_widget.setItem(4, 1, QTableWidgetItem(str(external_cracks_count)))

        # Metric 7: Max Internal Crack Length (color = blue)
        max_internal_crack_length = max(((length / csd) * 100 for length, color in crack_lengths if color == Qt.GlobalColor.blue), default=0)
        self.rating_table_widget.setItem(6, 1, QTableWidgetItem(f"{(max_internal_crack_length / csd) * 100:.2f}%"))

        # Metric 8: Max External Crack Length (color = yellow)
        max_external_crack_length = max(((length / csd) * 100 for length in external_crack_lengths), default=0)
        self.rating_table_widget.setItem(7, 1, QTableWidgetItem(f"{(max_external_crack_length / csd) * 100:.2f}%"))

        # Metric 9: Presence of Splits (color = red)
        presence_of_splits = any(color == Qt.GlobalColor.red for _, color in crack_lengths)
        self.rating_table_widget.setItem(8, 1, QTableWidgetItem("Yes" if presence_of_splits else "No"))

        # Metric 10: No cracks at all
        presence_of_cracks = len(crack_length) != 0

        # Find the row for "Overall Evaluation"
        overall_evaluation_row = None
        for row in range(self.rating_table_widget.rowCount()):
            if self.rating_table_widget.item(row, 0) and self.rating_table_widget.item(row, 0).text() == "Overall Evaluation":
                overall_evaluation_row = row
                break

        # Step 1: Evaluate Rating 5 (Any split at all)
        if presence_of_splits:
            assigned_rating = 5

        # Step 2: Evaluate Rating 0 (No cracks at all)
        elif not presence_of_cracks:
            assigned_rating = 0

        # Step 3: Evaluate sequentially for Ratings 1 through 4
        else:

            # Rating 4
            if all_cracks_combined_above_3xCSD or at_least_one_internal_crack_above_80_percent \
               or three_or_more_internal_cracks_above_50_percent or at_least_one_external_crack_above_80_percent:
                assigned_rating = 4

            # Rating 3
            elif two_or_less_50_80_internal_cracks and all_cracks_combined_below_3xCSD and all_external_cracks_below_50_percent:
                assigned_rating = 4
            
            # Rating 2
            elif all_cracks_below_50_percent and all_cracks_combined_below_2xCSD and all_external_cracks_below_25_percent:
                assigned_rating = 3

            # Rating 1
            elif all_cracks_combined_below_CSD and all_cracks_below_25_percent and all_external_cracks_below_10_percent:
                assigned_rating = 2

            """ # Rating 1
            rating_one_all_crack_condition = all((length / csd) * 100 < 25 for length, _ in crack_lengths) and combined_length_all_cracks < 100
            rating_one_external_condition = max_external_crack_length < 10
            print(f"Rating 1 all crack: {rating_one_all_crack_condition}")
            print(f"Rating 1 external condition: {rating_one_external_condition}")
            if (rating_one_all_crack_condition or rating_one_external_condition):
                assigned_rating = 1

            # Rating 2
            rating_two_all_crack_condition = all(25 <= (length / csd) * 100 < 50 for length, _ in crack_lengths) and 100 <= combined_length_all_cracks < 200
            rating_two_external_condition = 10 < max_external_crack_length <= 25
            print(f"Rating 2 all crack: {rating_two_all_crack_condition}")
            print(f"Rating 2 external condition: {rating_two_external_condition}")
            if rating_two_all_crack_condition or rating_two_external_condition:
                assigned_rating = 2

            # Rating 3
            rating_three_all_crack_condition = internal_cracks_count <= 2 and all(50 <= (length / csd) * 100 <= 80 for length, color in crack_lengths if color == Qt.GlobalColor.blue) and 200 <= combined_length_all_cracks < 300
            rating_three_external_condition = 25 < max_external_crack_length <= 50
            print(f"Rating 3 all crack: {rating_three_all_crack_condition}")
            print(f"Rating 3 external condition: {rating_three_external_condition}")
            if rating_three_all_crack_condition or rating_three_external_condition:
                assigned_rating = 3

            # Rating 4
            rating_four_all_crack_condition = combined_length_all_cracks >= 300 or max_internal_crack_length > 80 or \
                                              sum(1 for length, color in crack_lengths if color == Qt.GlobalColor.blue and (length / csd) * 100 > 50) >= 3
            rating_four_external_condition = max_external_crack_length > 50
            print(f"Rating 4 all crack: {rating_four_all_crack_condition}")
            print(f"Rating 4 external condition: {rating_four_external_condition}")
            if rating_four_all_crack_condition or rating_four_external_condition:
                assigned_rating = 4 """

        # Update Overall Evaluation
        if assigned_rating <= 3:
            overall_evaluation = "Pass"
        else:
            overall_evaluation = "Fail"

        overall_evaluation_row = next((row for row in range(self.rating_table_widget.rowCount())
                                    if self.rating_table_widget.item(row, 0) and self.rating_table_widget.item(row, 0).text() == "Overall Evaluation"), None)
        if overall_evaluation_row is not None:
            overall_evaluation_text = f"Rating: {assigned_rating} - {overall_evaluation}"
            self.rating_table_widget.setItem(overall_evaluation_row, 1, QTableWidgetItem(overall_evaluation_text))

            # Highlight the evaluation
            evaluation_item = self.rating_table_widget.item(overall_evaluation_row, 1)
            if evaluation_item:
                evaluation_item.setBackground(Qt.GlobalColor.green if overall_evaluation == "Pass" else Qt.GlobalColor.red)

        # Refresh the UI for the table to reflect changes
        self.rating_table_widget.viewport().update()