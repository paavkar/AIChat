import os
import re
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.layers import TextVectorization, Embedding, LSTM, Dense, Dropout, Bidirectional
from tensorflow.keras import Sequential
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import KFold
import matplotlib.pyplot as plt
import optuna
import emoji
import keras

class_weights = tf.constant([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.5])
@keras.saving.register_keras_serializable()
def weighted_binary_crossentropy(y_true, y_pred):
    """
    Computes a weighted binary crossentropy loss. Assumes that the last dimension
    of y_true and y_pred corresponds to the different labels.
    """
    # Compute the standard binary crossentropy per label.
    bce = tf.keras.backend.binary_crossentropy(y_true, y_pred)
    # Multiply each label's loss by its corresponding weight.
    weighted_bce = bce * class_weights
    # Return the mean loss over all samples and labels.
    return tf.reduce_mean(weighted_bce)

class SentimentAnalyser:
    def __init__(self, vocab_size=10000, max_length=100, batch_size=32):
        self.vocab_size = vocab_size
        self.max_length = max_length
        self.batch_size = batch_size

        self.text_vectorizer = None
        self.model = None
        self.mlb = None
        self.num_labels = None

        self.texts = None
        self.labels = None

        self.train_texts = None
        self.val_texts = None
        self.train_labels = None
        self.val_labels = None
        self.train_ds = None
        self.val_ds = None

        os.makedirs(os.path.join("..","models"), exist_ok=True)
        self.file_path = os.path.join("..", "models", "multi_label_sentiment.keras")

        self.label_mapping = {
            1: "anger",
            2: "anticipation",
            3: "disgust",
            4: "fear",
            5: "joy",
            6: "sadness",
            7: "surprise",
            8: "trust",
            9: "neutral"
        }

        self.custom_emoji_map = {
            "♪": ":music_note:"
        }

        if os.path.exists(self.file_path):
            self.load_model(self.file_path)

    def clean_text(self, text: str) -> str:
        """
        Clean the input text by:
        1. Converting emoji to text representations (e.g., 🎶 -> :musical_notes:).
        2. Removing unnecessary spaces before common punctuation marks.

        For example, transforms:
        "I love music 🎶 , and it makes me happy !" to:
        "I love music :musical_notes:, and it makes me happy!"
        """
        text = emoji.demojize(text)
        for char, replacement in self.custom_emoji_map.items():
            text = text.replace(char, replacement)
        # Remove spaces before common punctuation characters
        text = re.sub(r'\s+([,.!?;:-])', r'\1', text)
        return text.strip()

    def load_data(self):
        df_annotated = pd.read_csv('../datasets/en-annotated.tsv', sep='\t', header=None, names=['text', 'labels'])
        df_neutral = pd.read_csv('../datasets/neu_en.tsv', sep='\t', header=None, names=['labels', 'text'])
        df_neutral = df_neutral[['text', 'labels']]
        combined_df = pd.concat([df_annotated, df_neutral], ignore_index=True)
        combined_df['text'] = combined_df['text'].apply(self.clean_text)
        combined_df['labels'] = combined_df['labels'].astype(str).apply(
            lambda x: [int(lbl.strip()) for lbl in x.split(',')])

        combined_df = combined_df.sample(frac=1, random_state=42).reset_index(drop=True)
        print(f"Full dataset shape: {combined_df.shape}")

        # Convert the list of labels into a multi-hot encoded output.
        self.mlb = MultiLabelBinarizer()
        y = self.mlb.fit_transform(combined_df['labels'])
        self.num_labels = y.shape[1]

        self.texts = combined_df['text'].tolist()
        self.labels = y

    def prepare_datasets(self, test_size=0.2):
        train_texts, val_texts, train_labels, val_labels = train_test_split(
            self.texts, self.labels, test_size=test_size, random_state=42
        )
        self.train_texts = train_texts
        self.val_texts = val_texts
        self.train_labels = train_labels
        self.val_labels = val_labels

        self.train_ds = tf.data.Dataset.from_tensor_slices((train_texts, train_labels)).batch(self.batch_size)
        self.val_ds = tf.data.Dataset.from_tensor_slices((val_texts, val_labels)).batch(self.batch_size)

    def build_model(self, embedding_dim=32, lstm_units=64, dropout=0.2, recurrent_dropout=0.2, learning_rate=1e-3):
        self.text_vectorizer = TextVectorization(
            max_tokens=self.vocab_size,
            output_mode='int',
            output_sequence_length=self.max_length)
        self.text_vectorizer.adapt(self.train_texts)
        self.model = Sequential([
            self.text_vectorizer,
            Embedding(input_dim=self.vocab_size, output_dim=embedding_dim),
            Bidirectional(LSTM(lstm_units, dropout=dropout, recurrent_dropout=recurrent_dropout)),
            Dense(64, activation='relu'),
            Dropout(dropout),
            Dense(self.num_labels, activation='sigmoid')
        ])
        self.model.build((None,))
        model_optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
        self.model.compile(loss=weighted_binary_crossentropy, optimizer=model_optimizer,
                           metrics=['accuracy',
                                    tf.keras.metrics.BinaryAccuracy(name='binary_accuracy'),
                                    tf.keras.metrics.Precision(name='precision'),
                                    tf.keras.metrics.Recall(name='recall'),
                                    tf.keras.metrics.AUC(name='auc')])
        self.model.summary()

    def train(self, epochs=10):
        callbacks = [
            tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, min_lr=1e-5)
        ]
        hist = self.model.fit(self.train_ds, validation_data=self.val_ds, epochs=epochs, callbacks=callbacks)
        return hist

    def save_model(self, model_path):
        self.model.save(model_path)

    def load_model(self, model_path):
        self.model = tf.keras.models.load_model(model_path)

    def predict(self, texts):
        predictions = self.model.predict(tf.constant(texts, dtype=tf.string))
        return predictions

    def plot_loss_accuracy(self, hist):
        # Plot the loss
        plt.figure(figsize=(8, 4))
        plt.plot(hist.history['loss'], label='Training Loss')
        plt.plot(hist.history['val_loss'], label='Validation Loss')
        plt.title('Loss over Epochs')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.legend()
        plt.grid(True)
        plt.show()

        # Plot the accuracy
        plt.figure(figsize=(8, 4))
        plt.plot(hist.history['binary_accuracy'], label='Training Binary Accuracy')
        plt.plot(hist.history['val_binary_accuracy'], label='Validation Accuracy')
        plt.title('Binary Accuracy over Epochs')
        plt.xlabel('Epoch')
        plt.ylabel('Binary Accuracy')
        plt.legend()
        plt.grid(True)
        plt.show()

def objective(trial):
    embedding_dim = trial.suggest_categorical("embedding_dim", [16, 32, 64])
    batch_size = trial.suggest_categorical("batch_size", [16, 32, 64])
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 1e-2, log=True)
    lstm_units = trial.suggest_int("lstm_units", 32, 128, step=32)
    dropout = trial.suggest_float("dropout", 0.2, 0.5)
    recurrent_dropout = trial.suggest_float("recurrent_dropout", 0.1, 0.5)

    sa = SentimentAnalyser(vocab_size=10000, max_length=100, batch_size=batch_size)
    sa.load_data()

    texts = np.array(sa.texts)
    labels = np.array(sa.labels)

    n_folds = 5
    kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
    fold_losses = []

    index = 1
    for train_index, val_index in kf.split(texts):
        print(f"Current fold: {index}")
        X_train, X_val = texts[train_index].tolist(), texts[val_index].tolist()
        y_train, y_val = labels[train_index], labels[val_index]

        train_ds = tf.data.Dataset.from_tensor_slices((X_train, y_train)).batch(batch_size)
        val_ds = tf.data.Dataset.from_tensor_slices((X_val, y_val)).batch(batch_size)

        sa.text_vectorizer = TextVectorization(
            max_tokens=sa.vocab_size,
            output_mode='int',
            output_sequence_length=sa.max_length)
        sa.text_vectorizer.adapt(X_train)

        model = Sequential([
            sa.text_vectorizer,
            Embedding(input_dim=sa.vocab_size, output_dim=embedding_dim),
            Bidirectional(LSTM(lstm_units, dropout=dropout, recurrent_dropout=recurrent_dropout)),
            Dense(64, activation='relu'),
            Dropout(dropout),
            Dense(sa.num_labels, activation='sigmoid')
        ])
        model_optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
        model.compile(loss=weighted_binary_crossentropy, optimizer=model_optimizer,
                      metrics=['accuracy',
                               tf.keras.metrics.BinaryAccuracy(name='binary_accuracy'),
                               tf.keras.metrics.Precision(name='precision'),
                               tf.keras.metrics.Recall(name='recall'),
                               tf.keras.metrics.AUC(name='auc')])
        hist = model.fit(train_ds, validation_data=val_ds, epochs=10)

        fold_loss = hist.history["val_loss"][-1]
        fold_losses.append(fold_loss)
        index += 1

    avg_loss = np.mean(fold_losses)
    return avg_loss

    # sa.text_vectorizer = TextVectorization(
    #     max_tokens=sa.vocab_size,
    #     output_mode='int',
    #     output_sequence_length=sa.max_length)
    # sa.text_vectorizer.adapt(sa.train_texts)
    #
    # model = Sequential([
    #     sa.text_vectorizer,
    #     Embedding(input_dim=sa.vocab_size, output_dim=embedding_dim),
    #     Bidirectional(LSTM(lstm_units, dropout=dropout, recurrent_dropout=recurrent_dropout,
    #                        kernel_regularizer=l2(1e-4))),
    #     Dense(64, activation='relu', kernel_regularizer=l2(1e-4)),
    #     Dropout(dropout),
    #     Dense(sa.num_labels, activation='sigmoid')
    # ])
    # model_optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    # model.compile(loss='binary_crossentropy', optimizer=model_optimizer,
    #               metrics=['accuracy',
    #                        tf.keras.metrics.Precision(name='precision'),
    #                        tf.keras.metrics.Recall(name='recall'),
    #                        tf.keras.metrics.AUC(name='auc')])
    # callbacks = [
    #     tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
    #     # TFKerasPruningCallback(trial, monitor="val_loss")
    # ]
    # hist = model.fit(sa.train_ds, validation_data=sa.val_ds, epochs=10, callbacks=callbacks)
    # val_loss = hist.history["val_loss"][-1]
    # return val_loss

if __name__ == "__main__":
    use_optuna = False
    sentiment_model = SentimentAnalyser(vocab_size=10000, max_length=100, batch_size=16)
    if os.path.exists(sentiment_model.file_path):
        sentiment_model.load_model(sentiment_model.file_path)
    elif not use_optuna:
        sentiment_model.load_data()
        # sentiment_model.train_ds = tf.data.Dataset.from_tensor_slices(
        #     (sentiment_model.texts, sentiment_model.labels)).batch(sentiment_model.batch_size)
        sentiment_model.prepare_datasets(test_size=0.2)
        sentiment_model.build_model(16, 96, 0.23792599653083985, 0.3750530233524775, 0.00018470287691614877)
        history = sentiment_model.train(epochs=50)
        sentiment_model.plot_loss_accuracy(history)
        sentiment_model.save_model(sentiment_model.file_path)
    else:
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=20)
        print("Best trial:")
        trial = study.best_trial
        print("  Loss: {}".format(trial.value))
        print("  Params: ")
        for key, value in trial.params.items():
            print("    {}: {}".format(key, value))

        # After tuning, you can build and train a final model using the best parameters.
        best_params = trial.params
        sentiment_model = SentimentAnalyser(
            vocab_size=10000,
            max_length=100,
            batch_size=best_params["batch_size"]
        )
        sentiment_model.load_data()
        # sentiment_model.train_ds = tf.data.Dataset.from_tensor_slices(
        #     (sentiment_model.texts, sentiment_model.labels)).batch(sentiment_model.batch_size)
        sentiment_model.prepare_datasets(test_size=0.2)
        sentiment_model.build_model(best_params["embedding_dim"], best_params["lstm_units"],
                                    best_params["dropout"], best_params["recurrent_dropout"],
                                    best_params["learning_rate"])
        final_history = sentiment_model.train(epochs=50)
        sentiment_model.save_model(sentiment_model.file_path)
        sentiment_model.plot_loss_accuracy(final_history)

    test_texts = [
        "I really enjoyed the performance and the storyline.",
        "The meal was disappointing and the service was slow.",
        "🐢 are really great!",
        "I can't believe they lied to me again—it's absolutely revolting!",
        "I can hardly wait for the concert this weekend—it's going to be incredible!",
        "Walking alone at night always makes me uneasy, especially in unfamiliar places.",
        "I never expected him to step up like that, but he really proved himself!",
        "The meeting starts at 3 p.m. in room 204."
    ]
    preds = sentiment_model.predict(test_texts)
    # print("Predictions:\n", preds)

    for i, row in enumerate(preds):
        print(f"Text {i + 1}:")
        for j, value in enumerate(row):
            label = sentiment_model.label_mapping[j + 1]
            percentage = value * 100  # Convert to percentage
            print(f"  {label}: {percentage:.2f}%")
        print()

