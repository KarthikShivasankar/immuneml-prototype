import pandas as pd

from immuneML.IO.dataset_import.DataImport import DataImport
from immuneML.IO.dataset_import.DatasetImportParams import DatasetImportParams
from immuneML.data_model.dataset import Dataset
from immuneML.data_model.receptor.RegionType import RegionType
from immuneML.data_model.repertoire.Repertoire import Repertoire
from immuneML.util.ImportHelper import ImportHelper
from scripts.specification_util import update_docs_per_mapping


class IGoRImport(DataImport):
    """
    Imports data generated by `IGoR <https://github.com/qmarcou/IGoR>`_ simulations into a Repertoire-, or SequenceDataset.
    RepertoireDatasets should be used when making predictions per repertoire, such as predicting a disease state.
    SequenceDatasets should be used when predicting values for unpaired (single-chain) immune receptors, like
    antigen specificity.

    Note that you should run IGoR with the --CDR3 option specified, this tool imports the generated CDR3 files.
    Sequences with missing anchors are not imported, meaning only sequences with value '1' in the anchors_found column are imported.
    Nucleotide sequences are automatically translated to amino acid sequences.

    Reference: Quentin Marcou, Thierry Mora, Aleksandra M. Walczak
    ‘High-throughput immune repertoire analysis with IGoR’. Nature Communications, (2018)
    `doi.org/10.1038/s41467-018-02832-w <https://doi.org/10.1038/s41467-018-02832-w>`_.

    Arguments:

        path (str): This is the path to a directory with IGoR files to import. By default path is set to the current working directory.

        is_repertoire (bool): If True, this imports a RepertoireDataset. If False, it imports a SequenceDataset.
        By default, is_repertoire is set to True.

        metadata_file (str): Required for RepertoireDatasets. This parameter specifies the path to the metadata file.
        This is a csv file with columns filename, subject_id and arbitrary other columns which can be used as labels in instructions.
        Only the IGoR files included under the column 'filename' are imported into the RepertoireDataset.
        For setting SequenceDataset metadata, metadata_file is ignored, see metadata_column_mapping instead.

        import_with_stop_codon (bool): Whether sequences with stop codons should be included in the imported sequences.
        By default, import_with_stop_codon is False.

        import_out_of_frame (bool): Whether out of frame sequences (with value '0' in column is_inframe) should
        be included in the imported sequences. By default, import_out_of_frame is False.

        import_illegal_characters (bool): Whether to import sequences that contain illegal characters, i.e., characters
        that do not appear in the sequence alphabet (amino acids including stop codon '*', or nucleotides). When set to false, filtering is only
        applied to the sequence type of interest (when running immuneML in amino acid mode, only entries with illegal
        characters in the amino acid sequence are removed). By default import_illegal_characters is False.

        import_empty_nt_sequences (bool): imports sequences which have an empty nucleotide sequence field; can be True or False.
        By default, import_empty_nt_sequences is set to True.

        region_type (str): Which part of the sequence to import. By default, this value is set to IMGT_CDR3. This means the
        first and last amino acids are removed from the CDR3 sequence, as IGoR uses the IMGT junction. Specifying
        any other value will result in importing the sequences as they are.
        Valid values for region_type are the names of the :py:obj:`~immuneML.data_model.receptor.RegionType.RegionType` enum.

        column_mapping (dict): A mapping from IGoR column names to immuneML's internal data representation.
        For IGoR, this is by default set to:

        .. indent with spaces
        .. code-block:: yaml

            nt_CDR3: sequences
            seq_index: sequence_identifiers

        A custom column mapping can be specified here if necessary (for example; adding additional data fields if
        they are present in the IGoR file, or using alternative column names).
        Valid immuneML fields that can be specified here are defined by Repertoire.FIELDS

        column_mapping_synonyms (dict): This is a column mapping that can be used if a column could have alternative names.
        The formatting is the same as column_mapping. If some columns specified in column_mapping are not found in the file,
        the columns specified in column_mapping_synonyms are instead attempted to be loaded.
        For IGoR format, there is no default column_mapping_synonyms.

        metadata_column_mapping (dict): Specifies metadata for SequenceDatasets. This should specify a mapping similar
        to column_mapping where keys are IGoR column names and values are the names that are internally used in immuneML
        as metadata fields. These metadata fields can be used as prediction labels for SequenceDatasets.
        For IGoR format, there is no default metadata_column_mapping.
        For setting RepertoireDataset metadata, metadata_column_mapping is ignored, see metadata_file instead.

        separator (str): Column separator, for IGoR this is by default ",".


    YAML specification:

    .. indent with spaces
    .. code-block:: yaml

        my_igor_dataset:
            format: IGoR
            params:
                path: path/to/files/
                is_repertoire: True # whether to import a RepertoireDataset (True) or a SequenceDataset (False)
                metadata_file: path/to/metadata.csv # metadata file for RepertoireDataset
                metadata_column_mapping: # metadata column mapping IGoR: immuneML for SequenceDataset
                    igor_column_name1: metadata_label1
                    igor_column_name2: metadata_label2
                import_with_stop_codon: False # whether to include sequences with stop codon in the dataset
                import_out_of_frame: False # whether to include out of frame sequences in the dataset
                import_illegal_characters: False # remove sequences with illegal characters for the sequence_type being used
                import_empty_nt_sequences: True # keep sequences even though the nucleotide sequence might be empty
                # Optional fields with IGoR-specific defaults, only change when different behavior is required:
                separator: "," # column separator
                region_type: IMGT_CDR3 # what part of the sequence to import
                column_mapping: # column mapping IGoR: immuneML
                    nt_CDR3: sequences
                    seq_index: sequence_identifiers

    """
    CODON_TABLE = {
        'ATA': 'I', 'ATC': 'I', 'ATT': 'I', 'ATG': 'M',
        'ACA': 'T', 'ACC': 'T', 'ACG': 'T', 'ACT': 'T',
        'AAC': 'N', 'AAT': 'N', 'AAA': 'K', 'AAG': 'K',
        'AGC': 'S', 'AGT': 'S', 'AGA': 'R', 'AGG': 'R',
        'CTA': 'L', 'CTC': 'L', 'CTG': 'L', 'CTT': 'L',
        'CCA': 'P', 'CCC': 'P', 'CCG': 'P', 'CCT': 'P',
        'CAC': 'H', 'CAT': 'H', 'CAA': 'Q', 'CAG': 'Q',
        'CGA': 'R', 'CGC': 'R', 'CGG': 'R', 'CGT': 'R',
        'GTA': 'V', 'GTC': 'V', 'GTG': 'V', 'GTT': 'V',
        'GCA': 'A', 'GCC': 'A', 'GCG': 'A', 'GCT': 'A',
        'GAC': 'D', 'GAT': 'D', 'GAA': 'E', 'GAG': 'E',
        'GGA': 'G', 'GGC': 'G', 'GGG': 'G', 'GGT': 'G',
        'TCA': 'S', 'TCC': 'S', 'TCG': 'S', 'TCT': 'S',
        'TTC': 'F', 'TTT': 'F', 'TTA': 'L', 'TTG': 'L',
        'TAC': 'Y', 'TAT': 'Y', 'TAA': '*', 'TAG': '*',
        'TGC': 'C', 'TGT': 'C', 'TGA': '*', 'TGG': 'W',
    }

    @staticmethod
    def import_dataset(params: dict, dataset_name: str) -> Dataset:
        return ImportHelper.import_dataset(IGoRImport, params, dataset_name)

    @staticmethod
    def preprocess_dataframe(df: pd.DataFrame, params: DatasetImportParams):
        if "counts" not in df.columns:
            df["counts"] = 1

        df = df[df.anchors_found == "1"]

        if not params.import_out_of_frame:
            df = df[df.is_inframe == "1"]

        df["sequence_aas"] = df["sequences"].apply(IGoRImport.translate_sequence)

        if not params.import_with_stop_codon:
            no_stop_codon = ["*" not in seq for seq in df.sequence_aas]
            df = df[no_stop_codon]

        ImportHelper.junction_to_cdr3(df, params.region_type)
        df.loc[:, "region_types"] = params.region_type.name
        # note: import_empty_aa_sequences is set to true here; since IGoR doesnt output aa, this parameter is insensible
        ImportHelper.drop_empty_sequences(df, True, params.import_empty_nt_sequences)
        ImportHelper.drop_illegal_character_sequences(df, params.import_illegal_characters)

        # chain or at least receptorsequence?

        return df

    @staticmethod
    def translate_sequence(nt_seq):
        """
        Code inspired by: https://github.com/prestevez/dna2proteins/blob/master/dna2proteins.py
        """
        aa_seq = []
        end = len(nt_seq) - (len(nt_seq) % 3) - 1
        for i in range(0, end, 3):
            codon = nt_seq[i:i + 3]
            if codon in IGoRImport.CODON_TABLE:
                aminoacid = IGoRImport.CODON_TABLE[codon]
                aa_seq.append(aminoacid)
            else:
                aa_seq.append("_")
        return "".join(aa_seq)

    @staticmethod
    def get_documentation():
        doc = str(IGoRImport.__doc__)

        region_type_values = str([region_type.name for region_type in RegionType])[1:-1].replace("'", "`")
        repertoire_fields = list(Repertoire.FIELDS)
        repertoire_fields.remove("region_types")

        mapping = {
            "Valid values for region_type are the names of the :py:obj:`~immuneML.data_model.receptor.RegionType.RegionType` enum.": f"Valid values are {region_type_values}.",
            "Valid immuneML fields that can be specified here are defined by Repertoire.FIELDS": f"Valid immuneML fields that can be specified here are {repertoire_fields}."
        }
        doc = update_docs_per_mapping(doc, mapping)
        return doc